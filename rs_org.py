import os, sys, re, natsort
import shutil, glob
import tarfile
import nibabel as nb
from CPAC.AWS import aws_utils, fetch_creds
## Rockland Release Organization Script

#ipf=sys.argv[1]

ipdirec='/home/data/Incoming/rockland_sample/DiscSci_R8/coins_archives_extracted/'
opdirec='/home/data/Incoming/rockland_sample/DiscSci_R8/organized_symlinks/'


def convert_dcm_nii(ipdirec, cores):

    #Check for NIFTI conversion File and create
    if os.path.isfile(ipdirec+'niiconv.txt'):
	    os.remove(ipdirec+'niiconv.txt')
    niif=open(ipdirec+'niiconv.txt', 'w')

    #Find directories with DICOMs but no NIFTIs, and record
    for root, dirs, files in os.walk(ipdirec):
	if len(files) > 0 and (not any('.nii.gz' in f for f in files)) and (any('.dcm' in f for f in files)):
            print root
            niif.write('echo converting '+root+';'+'dcm2nii '+root+'/*.dcm\n')
    niif.close()

    print '## FINISHED INITIAL PASS ##'
    raw_input("### PAUSE ### Proceed to parallel commands?")
    #Run conversions
    os.system('cat '+ipdirec+'niiconv.txt | parallel -j '+cores)


def fix_bvs(ipdirec):
    for root, dirs, fs in os.walk(ipdirec):
        for f in fs:
            if '.bv' in f and 'diff' in f.lower():
                fpath=os.path.join(root, f)
                subfilepath=fpath.replace(ipdirec.rstrip('/'),'')
                subfilepath='/'.join(subfilepath.split('/')[2:-1])
                imgfolds=[g for g in glob.glob(ipdirec+'/*/'+subfilepath+'/*DIFF*') if '.bv' not in g]
                # If there is a DTI Folder, move bvs into it
                if len(imgfolds) > 1:
                    print 'Not Sure Too Many Folds', fpath
                elif len(imgfolds) == 1 and not os.path.isfile(imgfolds[0]+'/'+f.lower()):
                    shutil.move(fpath, imgfolds[0]+'/'+f.lower())
                    print 'Moving: ',fpath, imgfolds[0]+'/'+f.lower()
                elif len(imgfolds) == 1 and os.path.isfile(imgfolds[0]+'/'+f.lower()):
                    print 'Possible Duplicates: ',fpath, imgfolds[0]+'/'+f.lower()+'!!!!!'
                elif len(imgfolds) == 0 and 'diff' not in fpath.split('/')[-2].lower():
                    print 'Nowhere to put: ',fpath+'!!!!!'
                elif len(imgfolds) == 0 and 'diff' in fpath.split('/')[-2].lower():
                    print 'Fine ',fpath


def deob_reor(ipdirec, cores):

    #Create Error, Orient and Deoblique files
    errf=open(opdirec+'err_niiconv.txt', 'w')
    orientf=open(ipdirec+'orient_nii.txt', 'w')
    deobf=open(ipdirec+'deoblique_nii.txt', 'w')

    for root, dirs, fs in os.walk(ipdirec):
        if len(fs) > 0 and  any('.nii.gz' in f for f in fs):
            dirfiles=os.listdir(root)
            niftiname=root.split('/')[-1].lower()
            niftiname='_'.join(niftiname.split('_')[:-1])+'.nii.gz'
            numniftis=[nn  for nn in os.listdir(root) if '.nii.gz' in nn]
            print root+numniftis[0], niftiname
            if len(numniftis) == 1 and not os.path.isfile(root+'/'+niftiname):
                os.rename(root+'/'+numniftis[0], root+'/'+niftiname)
            if len(numniftis) == 3:
                filetouse=[ftu for ftu in numniftis if ftu[0] == 'o']
                print numniftis
                filetouse=filetouse[0]
                os.rename(root+'/'+filetouse, root+'/'+niftiname)
                for i in numniftis:
                    if os.path.isfile(root+'/'+i):
                        os.remove(root+'/'+i)

                if not any('_RPI' in f for f in fs):
                    deobf.write('3drefit -deoblique '+root+'/'+niftiname+'\n')
                    orientf.write('3dresample -orient RPI -inset '+root+'/'+niftiname+' -prefix '+root+'/'+niftiname.split('.')[0]+'_RPI.nii.gz\n')
                if any('.bv' in f for f in fs):
                    numbvs=[bv  for bv in os.listdir(root) if '.bv' in bv]
                    for bvfile in numbvs:
                        newbvname=niftiname.split('.')[0]+'.'+bvfile.split('.')[-1]		
                        os.rename(root+'/'+bvfile, root+'/'+newbvname)

    deobf.close()
    orientf.close()
    errf.close()

    raw_input("### PAUSE ### Proceed to parallel commands?")
    os.system('cat '+ipdirec+'deoblique_nii.txt | parallel -j '+cores)
    os.system('cat '+ipdirec+'orient_nii.txt | parallel -j '+cores)



def create_symlinks(ipdirec,opdirec):
    for root, dirs, fs in os.walk(ipdirec):
        for f in fs:
            #if ('.dcm' in f) or (('.nii.gz' in f) and ('_RPI' in f)) or (('.nii.gz' in f) and ('fieldmap' in f)) or (('.bv' in f) and ('TRACE' not in f)):
            if ('.dcm' in f) or (('.nii.gz' in f) and ('_RPI' in f)) or (('.bv' in f) and ('TRACE' not in f)):
            
                fpath=os.path.join(root,f)
	
                ## SUBID
                subid=re.findall('A00\d+', fpath)
                subid=subid[0]
			

                studyname='dummy'
                if 'long_child' in fpath:
                    studyname='clg'
                elif 'discoverysci' in fpath:
                    studyname='dsc'
                elif 'neurofeebac' in fpath:
                    studyname='nfb'

                ## VISITNAME
                visit=re.findall('\d+_V\w+', fpath)
                visitnum=visit[0].split('_V')[-1]

                #visitnum='2'

                ##IMAGENAME
                img=fpath.split('/')[-1].replace('_RPI','').lower()

                ## FOLDNAME
                newfold=fpath.split('/')[-2].lower()

                ##SESSIONNAME
                newsesh=studyname+'_'+visitnum

                
                print fpath.split('/')[-5:-2]			
                newpath=os.path.join(opdirec,subid,newsesh,newfold)
		
                print newpath+'/'+img

                if not os.path.isdir(newpath):
                    os.makedirs(newpath)
                #if os.path.isfile(newpath+'/'+img):
                #    os.remove(newpath+'/'+img)
                os.symlink(os.path.abspath(fpath),newpath+'/'+img)


def check_field_maps(opdirec):
    mycwd=os.getcwd()
    os.chdir(opdirec)
    scanmatch=re.compile(r'_00\d{2}$')
    for i in glob.glob('A*/*/'):
        imgfolds=natsort.natsorted([oi for oi in os.listdir(i) if 'fieldmap' in oi])

        print i,len(imgfolds)
        break
        if len(imgfolds) == 2:
            img1_vols=nb.Nifti1Image.load(imgfolds[0]).get_data()
        for iunq in ifset:
            nonunqs=[nu for nu in imgfolds if iunq in nu]
            if len(nonunqs) > 1:
                nums=[nu.split('_')[-1] for nu in nonunqs]
                topnum=max(nums)
                foldsdel=[fd for fd in nonunqs if topnum not in fd]
                print "Session "+i+" deleting:"+' '+','.join(foldsdel)
                for fd in foldsdel:
                    print fd
                    shutil.rmtree(i+fd+'/')
    for i in glob.glob('A*/*/'):
        imgfolds=os.listdir(i)
        for imf in imgfolds:
            if  scanmatch.search(imf) and not any(x in imf for x in exclude_key['substr_to_ex']):
                print "renaming:",i+imf, i+'_'.join(imf.split('_')[:-1])
                os.rename(i+imf, i+'_'.join(imf.split('_')[:-1]))
    os.chdir(mycwd)

def remove_failed_scans(opdirec,exclude_key):
    mycwd=os.getcwd()
    os.chdir(opdirec)
    scanmatch=re.compile(r'_00\d{2}$')
    for i in glob.glob('A*/*/'):
        imgfolds=os.listdir(i)
        ifset=set(['_'.join(ifold.split('_')[:-1]) for ifold in imgfolds if (scanmatch.search(ifold)) and not any(x in ifold for x in exclude_key['substr_to_ex'])])
        print i,len(ifset), len(imgfolds)
        for iunq in ifset:
            nonunqs=[nu for nu in imgfolds if iunq in nu]
            if len(nonunqs) > 1:
                nums=[nu.split('_')[-1] for nu in nonunqs]
                topnum=max(nums)
                foldsdel=[fd for fd in nonunqs if topnum not in fd]
                print "Session "+i+" deleting:"+' '+','.join(foldsdel)
                for fd in foldsdel:
                    print fd
                    shutil.rmtree(i+fd+'/')
    for i in glob.glob('A*/*/'):
        imgfolds=os.listdir(i)
        for imf in imgfolds:
            if  scanmatch.search(imf) and not any(x in imf for x in exclude_key['substr_to_ex']):
                print "renaming:",i+imf, i+'_'.join(imf.split('_')[:-1])
                os.rename(i+imf, i+'_'.join(imf.split('_')[:-1]))
    os.chdir(mycwd)

def get_size(target,filetypes):
    if os.path.isfile(target) and any(ft in target for ft in filetypes):
        print 'getting size: '+target
        return os.path.getsize(target)

    elif os.path.isdir(target):
        sze=0
        print 'getting size: '+target
        for root,dirs,fs in os.walk(target):
            for f in fs:
                fpath=os.path.join(root,f)
                if any(ft in f for ft in filetypes):
                    sze+=os.path.getsize(fpath)
        return sze

    else:
        raise(ValueError('Please specify file or directory'))

def create_tarfile(ipfiles, opname):

    tf = tarfile.open(opname, 'w:gz')
    tf.dereference=True
    for ipf in ipfiles:
        print ipf
        tf.add(ipf)
    tf.close()

def tar_dirs(ipdir,opdir,filesizerange,filetypes):
    #folds_to_check=sorted(glob.glob(ipdir+'/*'))
    os.chdir(ipdir)
    folds_to_check=sorted(glob.glob('*'))
    folds_to_tar=[]
    items_to_tar=[]
    foldtemp=[]
    for ftc in folds_to_check:
        print 'checking: '+ftc
        folds_to_tar=folds_to_tar+foldtemp
        folds_to_tar.append(ftc)
        sizecheck=sum([get_size(ftt,filetypes) for ftt in folds_to_tar])/1024.**3
        print folds_to_tar,sizecheck
        if sizecheck < filesizerange[0]:
            pass
        elif sizecheck >= filesizerange[0] and sizecheck <= filesizerange[1]:
            print 'tarring: '+' '.join(folds_to_tar)
            for ftt in folds_to_tar:
                for root,dirs,fs in os.walk(ftt):
                    for f in fs:
                        if any(ft in f for ft in filetypes):
                            items_to_tar.append(os.path.join(root,f))
            create_tarfile(items_to_tar,'_'.join([folds_to_tar[0].replace('/','').replace('.',''),folds_to_tar[-1].replace('/','').replace('.','')])+'.tar.gz')
            items_to_tar=[]
            folds_to_tar=[]

        elif sizecheck > filesizerange[1]:
            print 'reducing size'
            while sizecheck > filesizerange[1]:
                foldtemp.append(folds_to_tar[-1])
                del folds_to_tar[-1]
                sizecheck=sum([get_size(ftt,filetypes) for ftt in folds_to_tar])/1024.**3

    if len(folds_to_tar) > 0:
        print 'tarring: '+' '.join(folds_to_tar)
        for ftt in folds_to_tar:
            for root,dirs,fs in os.walk(ftt):
                for f in fs:
                    if any(ft in f for ft in filetypes):
                        items_to_tar.append(os.path.join(root,f))
        create_tarfile(items_to_tar,'_'.join([folds_to_tar[0].replace('/','').replace('.',''),folds_to_tar[-1].replace('/','').replace('.','')])+'.tar.gz')
         
                        
def compare_warehouse_coins(warehouse,coins):
    coins_dict={}
    for root, dirs, fs in os.walk(coins):
        for f in fs:
            if any(x in f for x in ['.nii','.dcm','.bv']):
                fpath=os.path.join(root,f)
                subid=re.findall('A00\d+', fpath)
                subid=subid[0]

                studyname='dummy'
                if 'long_child' in fpath:
                    studyname='clg'
                elif 'discoverysci' in fpath:
                    studyname='dsc'
                elif 'neurofeebac':
                    studyname='nfb'

                ## VISITNAME
                visit=re.findall('\d+_V\w+', fpath)
                visitnum=visit[0].split('_V')[-1]

                ##IMAGENAME
                img=fpath.split('/')[-1].replace('_RPI','').lower()

                ## FOLDNAME
                newfold=fpath.split('/')[-2].lower()

                ##SESSIONNAME
                newsesh=studyname+'_'+visitnum

                coins_dict.setdefault(subid,{})
                coins_dict[subid].setdefault(newsesh,[])
                if newfold not in coins_dict[subid][newsesh]:
                    coins_dict[subid].setdefault(newsesh,[]).append(newfold)

    warehouse_dict={}
    print 'warehouse'
    for root, dirs, fs in os.walk(warehouse):
        for f in fs:
            if any(x in f for x in ['.nii','.dcm','.bv']):
                fpath=os.path.join(root,f)

                subid=re.findall('M109\d+', fpath)
                subid=subid[0]

                visit=[re.findall(prefix+'[AREP2-5]+',fpath) for prefix in ['DS','NFB','CLG']]
                visit=[x for v in visit for x in v]
                if not visit:
                    visit='Unknown'
                else:
                    visit=visit[0]

                if 'CLG' in visit:
                    visit='clg_'+visit.replace('CLG','')
                elif 'DS' in visit:
                    visit='dsc_'+visit.replace('DS','')
                elif 'NFB' in visit:
                    visit='nfb_'+visit.replace('NFB','')

                ## FOLDNAME
                newfold=fpath.split('/')[-2].lower()

                vdate=re.findall('\d{4}-\d{2}-\d{2}', fpath)
                vdate=vdate[0]
                #print fpath

                vtime=re.findall('_\d{6}\/', fpath)
                if vtime:
                    vtime=vtime[0].replace('/','') .replace('_','')
	        else:
                    vtime='unknown'           
                #print subid,visit,newfold,vtime


		visit=visit+';'+vdate+';'+vtime

                warehouse_dict.setdefault(subid,{})
                warehouse_dict[subid].setdefault(visit,[])
                if newfold not in warehouse_dict[subid][visit]:
                    warehouse_dict[subid].setdefault(visit,[]).append(newfold)


    return warehouse_dict,coins_dict


def compare_dicts(coinsdict,warehousedict,subkey):
    for key1, value1 in sorted(coins.iteritems()):
        #print key
        if  subkey.ursi[subkey.anon == key].values[0] in ware.keys():
            ursi=subkey.ursi[subkey.anon == key].values[0]
            print  key, ursi
            for key2, value2 in sorted(coins[key1].iteritems()):
                seshmatch=[dcmsesh for dcmsesh in ware[ursi].keys() if key2 in dcmsesh]
                print seshmatch
                print coins[key1].keys(), ware[ursi].keys()
                if len(seshmatch) == 1:
                    print set(coins[key1][key2]).symmetric_difference(set(ware[ursi][seshmatch[0]]))
                    
                    
        else:
            print key, "Not in DCM Warehouse"

def upload_dir_contents(ipdir,s3path, bucketname, creds):
    srclist=[os.path.abspath(g) for g in glob.glob(ipdir+'/*')]
    destlist=[s3path+'/'+s.split('/')[-1] for s in srclist]
    bucket=fetch_creds.return_bucket(creds, bucketname)
    aws_utils.s3_upload(bucket,srclist,destlist)

