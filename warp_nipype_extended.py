import nipype.pipeline.engine as pe
from nipype.interfaces import afni,fsl
import nipype.interfaces.io as nio
import nipype.interfaces.utility as util
import nipype
import os,glob,sys


## Intialize variables and workflow
globaldir='/data/Projects/epi_dist_correction/'
workdir=os.path.join(globaldir, 'niwork')
preproc = pe.Workflow(name='preprocflow')
preproc.base_dir = workdir

sublist=[g.split('/')[-1] for g in glob.glob(globaldir+'organized_inputs/*')][0:4]
seslist=list(set([g.split('/')[-1] for g in glob.glob(globaldir+'organized_inputs/*/*')]))



## Setup data managment nodes

infosource = pe.Node(util.IdentityInterface(fields=['subject_id','session_id']),name="infosource")
infosource.iterables = [('subject_id', sublist),('session_id', seslist)]

templates={
'anat':'organized_inputs/{subject_id}/{session_id}/dmn_fb_anat_defaced/dmn_fb_anat_defaced.nii.gz',\
'func':'organized_inputs/{subject_id}/{session_id}/msit/msit.nii.gz',\
'fmap_mag':'organized_inputs/{subject_id}/{session_id}/fieldmap_mag/fieldmap.nii.gz',\
'fmap_pha':'organized_inputs/{subject_id}/{session_id}/fieldmap_pha/fieldmap.nii.gz'}
selectfiles = pe.Node(nio.SelectFiles(templates,base_directory=globaldir),name="selectfiles")



datasink = pe.Node(nio.DataSink(base_directory=globaldir, container=workdir),name="datasink")


## Specify commands to be run

# Extract first three volumes from fmri
fslroi = pe.Node(interface=fsl.ExtractROI(),name='fslroi')
fslroi.inputs.t_min=0
fslroi.inputs.t_size=3

# Skullstrip
skullstrip = pe.Node(interface=afni.preprocess.SkullStrip(),name='skullstrip')
skullstrip.inputs.outputtype='NIFTI_GZ'

skullstrip_anat = pe.Node(interface=afni.preprocess.SkullStrip(),name='skullstrip_anat')
skullstrip_anat.inputs.outputtype='NIFTI_GZ'

# Prepare Fieldmap
prepare = pe.Node(interface=fsl.epi.PrepareFieldmap(),name='prepare')
prepare.inputs.output_type = "NIFTI_GZ"
prepare.inputs.delta_TE = 2.46

# Co-Register EPI and Correct field inhomogeniety distortions
#epireg = pe.Node(interface=fsl.epi.EpiReg(), name='epireg')
#epireg.inputs.echospacing=0.00046
#epireg.inputs.pedir='-y'
#epireg.inputs.output_type='NIFTI_GZ'

# White Matter Segmentation (Make sure to generate edge map)
segment=pe.Node(interface=fsl.FAST(),name='segment')

wmbinmap=
#fast -o opname_fast anat_ss
#fslmaths opname_fast_pve_2 -thr 0.5 -bin opname_fast_wmseg
#fslmaths opname_fast_wmseg -edge -bin -mas opname_fast_wmseg opname_fast_wmedge

# Flirt Pre-Alignment, using skullstripped T1 as reference
#flirt -ref anat_ss -in epi -dof 6 -omat opname_init.mat

# Register Field Map to Structural
#flirt -in fmap_mag_ss -ref anat_ss -dof 6 -omat opname_fieldmap2str_init.mat
#flirt -in fmap_mag -ref anat -dof 6 -init opname_fieldmap2str_init.mat -omat opname_fieldmap2str.mat -out opname_fieldmap2str -nosearch

# Unmask the Field Map
#fslmaths fmap_mag_ss -abs -bin ${vout}_fieldmaprads_mask
#fslmaths fmap_prep -abs -bin -mul opname_fieldmaprads_mask opname_fieldmaprads_mask
#fugue --loadfmap=fmap_prep --mask=opname_fieldmaprads_mask --unmaskfmap --savefmap=$opname_fieldmaprads_unmasked --unwarpdir=-y # the direction here should take into account the initial affine (it needs to be the direction in the EPI)
	
# NEW HACK to fix extrapolation when fieldmap is too small
applywarp -i opname_fieldmaprads_unmasked -r anat_ss --premat=opname_fieldmap2str.mat -o opname_fieldmaprads2str_pad0
fslmaths opname_fieldmaprads2str_pad0 -abs -bin opname_fieldmaprads2str_innermask
fugue --loadfmap=opname_fieldmaprads2str_pad0 --mask=opname_fieldmaprads2str_innermask --unmaskfmap --unwarpdir=y- --savefmap=opname_fieldmaprads2str_dilated
fslmaths opname_fieldmaprads2str_dilated opname_fieldmaprads2str

# run bbr with fieldmap
if [ $use_weighting = yes ] ; then wopt="-refweight $refweight"; else wopt=""; fi
flirt -ref anat_ss -in msit -dof 6 -cost bbr -wmseg opname_fast_wmseg -init opname_init.mat -omat opname.mat -out opname_1vol -schedule bbr.sch -echospacing ${dwell} -pedir y- -fieldmap opname_fieldmaprads2str $wopt


# Making warp fields and applying registration to EPI series
convert_xfm -omat opname_inv.mat -inverse opname.mat
convert_xfm -omat opname_fieldmaprads2epi.mat -concat opname_inv.mat opname_fieldmap2str.mat
applywarp -i opname_fieldmaprads_unmasked -r msit --premat=opname_fieldmaprads2epi.mat -o opname_fieldmaprads2epi
fslmaths opname_fieldmaprads2epi -abs -bin opname_fieldmaprads2epi_mask
fugue --loadfmap=opname_fieldmaprads2epi --mask=opname_fieldmaprads2epi_mask --saveshift=opname_fieldmaprads2epi_shift --unmaskshift --dwell=${dwell} --unwarpdir=-y
convertwarp -r anat_ss -s opname_fieldmaprads2epi_shift --postmat=opname.mat -o opname_warp --shiftdir=y- --relout
applywarp -i msit -r anat_ss -o opname -w opname_warp --interp=spline --rel



## Connect nodes and run workflow

preproc.connect([ 
                 (infosource,selectfiles,[('subject_id', 'subject_id'),('session_id', 'session_id')]),
                 (selectfiles,fslroi,[('func','in_file')]), 
                 (fslroi,datasink,[('roi_file','@3vol')]),
                 (selectfiles,skullstrip,[('fmap_mag','in_file')]),
                 (skullstrip,datasink,[('out_file','@mag_ss')]),
                 (selectfiles,skullstrip_anat,[('anat','in_file')]),
                 (skullstrip_anat,datasink,[('out_file','@anat_ss')]),
                 (skullstrip,prepare,[('out_file','in_magnitude')]),
                 (selectfiles,prepare,[('fmap_pha','in_phase')]),
                 (prepare,datasink,[('out_fieldmap','@fmap_prep')]),
                 (selectfiles,epireg,[('func','epi')]),
                 (selectfiles,epireg,[('anat','t1_head')]),
                 (selectfiles,epireg,[('fmap_mag','fmapmag')]),
                 (skullstrip_anat,epireg,[('out_file','t1_brain')]),
                 (skullstrip,epireg,[('out_file','fmapmagbrain')]),
                 (prepare,epireg,[('out_fieldmap','fmap')]),
                 (epireg,datasink,[('out_file','@epireg')])
                ])


preproc.run('MultiProc',plugin_args={'n_procs':4})
