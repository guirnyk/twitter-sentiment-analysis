"""Fabric deployment file for remote model training.

TODO(andrei): fabric is kind of deprecated. Use 'pyinvoke'.

Uses a Python 3 fork of Fabric (http://www.fabfile.org/).
Please install 'Fabric3' to use this, NOT the vanilla 'fabric'.

```bash
    pip install Fabric3
```

Make sure that 'env.hosts' points to wherever you want to train your model, and
that the remote host has tensorflow installed.

Example:
    `fab euler`        rsync data to Euler and start a training session.
"""

from __future__ import with_statement

import os

from fabric.api import *
from fabric.contrib.project import rsync_project as rsync

env.use_ssh_config = True

# Necessary for GCE.
# env.key_filename = '~/.ssh/google_compute_engine'


def latest_run_id():
    """Returns the ID of the most recent TF run."""
    # TODO(andrei): Nicer way of doing this?
    return "ls -t ~/deploy/data/runs | cat | head -n1"


# Hint: set your appropriate user for Euler in your '~/.ssh/config'!
@hosts('euler')
def euler(sub='run'):
    # If something stops working, make sure you're 'rsync'ing everything you
    # need to the remote host! Also, make sure TensorFlow itself isn't broken
    # on Euler because of all the weird patching required to get it working in
    # the first place.

    if sub == 'run':
        _run_euler()
    elif sub == 'status':
        run('bjobs')
    elif sub == 'fetch':
        # TODO(andrei): Do this in nicer way.
        raise ValueError("This may download the wrong thing(s) from Euler."
                         " Disable this error and use at your own risk!")
        _download_results('euler')
    else:
        raise ValueError("Unknown Euler action: {0}".format(sub))


def _run_euler():
    print("Will train TF model remotely on Euler.")
    sync_data_and_code()

    # Custom Euler stuff.
    put(local_path='./tensor_hello.py',
        remote_path=os.path.join('~/deploy', 'tensor_hello.py'))
    put(local_path='./euler_voodoo.sh',
        remote_path=os.path.join('~/deploy', 'euler_voodoo.sh'))
    print("Uploaded data and code. Starting to train.")

    with cd('deploy'):
        # TODO(andrei): Also train embeddings on validation data.
        # TODO(andrei): Run on scratch instead of in '~'.
        # Creates a timestamped folder in which to run.
        ts = '$(date +%Y%m%dT%H%M%S)'
        # Hint: Replace the "heavy" 'train_model' call with 'tensor_hello' if
        # you just want to test things out.
        tf_command = ('t=' + ts + ' && mkdir $t && cd $t &&'
                      ' source ../euler_voodoo.sh &&'
                      # Use many cores and run for up to two hours.
                      ' bsub -n 48 -W 12:00'
                      # This flag tells 'bsub' to send an email to the submitter
                      # when the job starts.
                      ' -B'
                      ' LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$HOME/ext/lib" "$HOME"/ext/lib/ld-2.23.so "$HOME"/.venv/bin/python3'
                      # TODO(andrei): Pass these parameters as arguments to fabric.
                      ' ../train_model.py --num_epochs 9'
                      ' --data_root ../data'
                      ' --batch_size 256 --evaluate_every 2000'
                      ' --checkpoint_every 20000 --output_every 1000')
        run(tf_command, shell_escape=False, shell=False)


def gce():
    raise RuntimeError("We should probably stick to Euler and maybe AWS for the"
                       " time being.")

    # TODO(andrei): Use 'screen' in case connection dies.

    print("Will train TF model remotely on Google Compute Engine.")
    sync_data_and_code()
    print("Uploaded data and code. Starting to train.")

    with cd('deploy'):
        # TODO(andrei): Pass these parameters as arguments to fabric.
        run('python -m train_model --num_epochs 20'
            ' --batch_size 256 --evaluate_every 250'
            ' --checkpoint_every 1000 --output_every 100')

    _download_results('gce')


def sync_data_and_code():
    run('mkdir -p ~/deploy/data/preprocessing')

    folder = os.path.join('data', 'preprocessing') + '/'
    # This does no tilde expansion, and this is what we want.
    remote_folder = os.path.join('~/deploy', folder)

    # This syncs the data (needs to be preprocessed in advance).
    rsync(local_dir=folder, remote_dir=remote_folder,
          exclude=['*.txt'])

    put(local_path='./train_model.py',
        remote_path=os.path.join('~/deploy', 'train_model.py'))

    # This syncs the model code.
    rsync(local_dir='model', remote_dir='deploy')


def _download_results(prefix):
    """Downloads all the TF output data from the remote host."""
    local('mkdir -p data/runs/{0}'.format(prefix))

    # TODO(andrei): Nicer folder structure.
    # TODO(andrei): Random tmp folder for maximum Euler compatibility.
    run('mkdir -p /tmp/last_tf_run')
    run('cp -R ~/deploy/data/runs/$({})/ /tmp/last_tf_run'.format(latest_run_id()),
        shell_escape=False, shell=False)
    get(remote_path='/tmp/last_tf_run/*',
        local_path='data/runs/{0}'.format(prefix))
    print("Downloaded the pipeline results.")


def tb():
    """See: 'tensorboard'"""
    return tensorboard()


def tensorboard():
    """Starts a remote tensorboard to see your pipeline's status.

    TODO(andrei): Run in screen.

    Make sure you allow TCP on port 6006 for the remote machine!
    """

    with cd('deploy'):
        tb_cmd = 'tensorboard --logdir data/runs'
        screen = "screen -dmS tensorboard_screen bash -c '{}'".format(tb_cmd)
        print(screen)
        run(screen, pty=False)


def latest_tb():
    """See: 'latest_tensorboard'"""
    return latest_tensorboard()


def latest_tensorboard():
    """
    Uses the latest log dir as a source.
    """
    with cd('deploy'):
        # This sets logdir to the most recent run.
        run('tensorboard --logdir data/runs/$(ls -t data/runs | cat | head -n1)/summaries',
            shell_escape=False, shell=False)


def kill_tb():
    return kill_tensorboard()


def kill_tensorboard():
    run('killall tensorboard')


def host_type():
    """An example of a Fabric command."""

    # This runs on your machine.
    local('uname -a')

    # This runs on the remote host(s) specified by the -H flag. If none are
    # specified, this runs on all 'env.hosts'.
    run('uname -a && lsb_release -a')
    run('pwd')
    with cd('/tmp'):
        run('pwd')

