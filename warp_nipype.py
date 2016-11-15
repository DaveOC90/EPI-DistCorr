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

sublist=[g.split('/')[-1] for g in glob.glob(globaldir+'organized_inputs/*')]
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
epireg = pe.Node(interface=fsl.epi.EpiReg(), name='epireg')
epireg.inputs.echospacing=0.00046
epireg.inputs.pedir='-y'
epireg.inputs.output_type='NIFTI_GZ'


## COnenct nodes and run workflow

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
