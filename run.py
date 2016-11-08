import os,glob
import natsort
import nibabel as nb
import sys

sub=sys.argv[1]

#subs=[sorted(glob.glob('A00*'))[0]]
subs=[sub]
#subs=sorted(glob.glob('A00*'))

skullstrip={
'type':'afni',
'thresh':0.3}



workdir='/data/Projects/epi_dist_correction/working/'


for sub in subs:
    subwdir=os.path.join(workdir,sub)

    subsesh=glob.glob(sub+'/*V3/')

    if len(subsesh) != 1:
        raise Exception('Wrong no of subs/sessions:'+' '.join(subsesh))
    else:
        subsesh=subsesh[0]

    print sub

    if not os.path.isdir(subwdir):
        os.makedirs(subwdir)


    msit=glob.glob(subsesh+'MSIT*/*RPI.nii.gz')

    if len(msit) != 1:
        raise Exception('Wrong no of MSIT:'+' '.join(msit))
    else:
        msit=msit[0]


    print '### Extracting first three volumes of MSIT ###'

    msit_3vol=os.path.join(subwdir,'msit_3vol.nii.gz')
    #os.system('fslroi %s %s 0 3' % (msit,msit_3vol))

    fmaps=glob.glob(subsesh+'FieldMap*/*RPI.nii.gz')

    if len(fmaps) != 2:
        raise Exception('Wrong no of Fmaps:'+' '.join(fmaps))



    fmap_mag=natsort.natsorted(fmaps)[0]
    if len(nb.Nifti1Image.load(fmap_mag).shape) != 4 and nb.Nifti1Image.load(fmap_mag).shape[3] != 2:
       raise Exception('Not sure this is a magnitude image: '+fmap_mag)


    fmap_pha=natsort.natsorted(fmaps)[1]

    if len(nb.Nifti1Image.load(fmap_pha).shape) != 3:
        raise Exception('Not sure this is a magnitude image: '+fmap_pha)
       

    print '### Skull Stripping Field Map Magnitude Image ###'

    if skullstrip['type'] == 'afni':
        fmap_mag_ss=os.path.join(subwdir,'fmap_mag_3dss.nii.gz')
        #os.system('3dSkullStrip -input %s -prefix %s'%(fmap_mag,fmap_mag_ss))

    elif skullstrip['type'] == 'fsl':
        thr=skullstrip['thresh']
        fmap_mag_ss=os.path.join(subwdir,'fmap_mag_bet%s.nii.gz'%(str(thr).replace('.','')))
        #os.system('bet %s %s -f %0.2f' % (fmap_mag,fmap_mag_ss,thr) )

    print '### Running FSL Prepare Field Map ###'

    fmap_prep=os.path.join(subwdir,'fmap_prep')
    #os.system('fsl_prepare_fieldmap SIEMENS %s %s %s 2.46'%(fmap_pha,fmap_mag_ss,fmap_prep))

    reg_dict={'smooth':'-s 3', \
              'despike':'--despike', \
              'medfilt':'-m'}

    print '### Regularizing Field Map ###'
    for regk in reg_dict.keys():
        print regk
        fmap_prep_reg=os.path.join(subwdir,'fmap_prep_'+regk)
        #os.system('fugue --loadfmap=%s %s --savefmap=%s'%(fmap_prep,reg_dict[regk],fmap_prep_reg))
    

    anats=glob.glob(subsesh+'DMN_FB_ANAT_DEFACED*/*RPI.nii.gz')
    if len(anats) != 1:
        raise Exception('Wrong no of anats:',' '.join(anats))

    else:
        anat=anats[0]

    print '### Skull Stripping Anat ###'

    anat_ss=os.path.join(subwdir,'anat_ss.nii.gz')
    #os.system('3dSkullStrip -input %s -prefix %s' % (anat,anat_ss))


    print '### Running EPI Reg with and without fmap correction###'
    for regk in reg_dict.keys():
        print regk
        msit_epireg=os.path.join(subwdir,'msit_epireg_'+regk)
        msit_epireg_nofmap=os.path.join(subwdir,'msit_epireg_nofmapcorr_'+regk)
        fmap_prep_reg=os.path.join(subwdir,'fmap_prep_'+regk)
        #os.system('epi_reg --epi=%s --t1=%s --t1brain=%s --out=%s --pedir=y- --echospacing=0.00046 --fmap=%s --fmapmag=%s --fmapmagbrain=%s' \
        #    % (msit_3vol,anat,anat_ss,msit_epireg, fmap_prep_reg+'.nii.gz', fmap_mag, fmap_mag_ss+'.nii.gz'))
        os.system('epi_reg --epi=%s --t1=%s --t1brain=%s --out=%s' \
            % (msit_3vol,anat,anat_ss,msit_epireg_nofmap))

