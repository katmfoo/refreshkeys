import distutils.spawn
import sys
import os
import json
import subprocess
import pexpect
import signal

# refreshkeys, script to refresh ssh/gpg key passphrases in keychain using 1password
# source: https://github.com/pricheal/refreshkeys

# catch sigint
def signal_handler(sig, frame):
    sys.exit("\nFailed, interrupted")
signal.signal(signal.SIGINT, signal_handler)

def program_installed(name: str) -> bool:
    """Returns whether or not the given program is installed on the system"""
    return distutils.spawn.find_executable(name) is not None

def get_passphrases():
    """Gets ssh and gpg key passphrases from 1password"""

    OP_ADDRESS = "https://my.1password.com"
    OP_EMAIL = "patrickricheal@gmail.com"

    # determine if we need to do the first time 1password signin or not
    first_time_signin = True
    try:
        path = os.getenv('HOME') + '/.op/config'
        with open(path) as f:
            data = json.load(f)
        for account in data['accounts']:
            if account['url'] == OP_ADDRESS and account['email'] == OP_EMAIL:
                first_time_signin = False
                break
    except:
        pass

    # signin to 1password cli to get token
    if first_time_signin:
        # not sure why, but can't do stderr=subprocess.DEVNULL otherwise the signin prompt is not shown (not the case for the non first time signin)
        process = subprocess.run('op signin my ' + OP_EMAIL + ' --raw', shell=True, stdout=subprocess.PIPE)
    else:
        process = subprocess.run('op signin my --raw', shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode != 0:
        sys.exit("Failed, 1password login unsuccessful")
    TOKEN = process.stdout.decode('utf-8')

    # get key passphrases from 1password
    try:
        # get list of documents from 1password
        process = subprocess.run('op list documents --session ' + TOKEN, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        op_documents = json.loads(process.stdout.decode('utf-8'))

        # get ssh/gpg document uuids based on the document titles
        for document in op_documents:
            if document['overview']['title'] == "SSH private key":
                ssh_key_uuid = document['uuid']
            if document['overview']['title'] == "GPG private key":
                gpg_key_uuid = document['uuid']

        def get_passphrase_from_item(document_uuid):
            """Function to get passphrase from 1password item given its uuid"""
            process = subprocess.run('op get item ' + document_uuid + " --session " + TOKEN, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            ssh_document = json.loads(process.stdout.decode('utf-8'))
            for section in ssh_document['details']['sections']:
                for field in section['fields']:
                    if field['t'] == 'passphrase':
                        return field['v']
            return None

        # get passphrases
        ssh_key_passphrase = get_passphrase_from_item(ssh_key_uuid)
        gpg_key_passphrase = get_passphrase_from_item(gpg_key_uuid)

        if not ssh_key_passphrase or not gpg_key_passphrase:
            raise Exception()

        return {'ssh': ssh_key_passphrase, 'gpg': gpg_key_passphrase}

    except:
        sys.exit("Failed, 1password login unsuccessful")

def main():
    """Main logic of script"""

    # determine if we are in 'eval mode' (outputs commands from keychain to be evaled)
    eval_mode = False
    for arg in sys.argv[1:]:
        if arg == '--eval':
            eval_mode = True

    # determine if we are in 'if needed mode' (only asks for password if necessary)
    if_needed = False
    for arg in sys.argv[1:]:
        if arg == '--if-needed':
            if_needed = True

    # ensure necessary command line tools are installed
    if not program_installed('jq'): sys.exit('Failed, jq not installed')
    if not program_installed('op'): sys.exit('Failed, 1password cli not installed')
    if not program_installed('keychain'): sys.exit('Failed, keychain not installed')

    # run keychain
    process = pexpect.spawn('keychain --eval --quiet --nogui --timeout 1440 --agents ssh,gpg id_rsa 2A70B83FD3493624')

    # initiate passphrases (so we only do it in one of the two below iterations)
    passphrases = None

    # whether or not we actually refreshed an agent
    actually_refreshed = False

    # attempt the following twice (once for ssh and the other for gpg)
    for i in range(0, 2):

        # expect either ssh prompt, gpg prompt, or eof (eof if neither passphrase is needed)
        index = process.expect(['Enter passphrase for', 'Please enter the passphrase', pexpect.EOF])

        # if in 'if needed mode', only get passphrases from 1password if we got a prompt from
        # keychain (if not in 'if needed mode', always prompt)
        if (index == 0 or index == 1 or not if_needed) and not passphrases:
            passphrases = get_passphrases()

        # if we are on the first iteration (so the first expect call) and in 'eval mode', get the eval
        # output from keychain and print it to standard out
        if i == 0 and eval_mode:
            eval_output = process.before.decode('utf-8').replace('\r', '')
            print(eval_output)

        # send passphrase if necessary, or finish
        if index == 0: # ssh prompt
            process.sendline(passphrases['ssh'])
            actually_refreshed = True
        elif index == 1: # gpg prompt
            process.sendline(passphrases['gpg'])
            actually_refreshed = True
        elif index == 2: # no prompt (eof), we are done
            break

    # wait for process to finish before ending script
    process.wait()

    # output success message
    if actually_refreshed and not eval_mode:
        print("Success, keychain refreshed")

if __name__ == "__main__":
    main()
