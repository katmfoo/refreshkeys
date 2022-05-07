import distutils.spawn
import sys
import os
import json
import subprocess
import pexpect
import signal
import re

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

    # make sure the 1password account exists locally
    process = subprocess.run('op account list --format json', shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode != 0:
        sys.exit("Failed, 1password couldn't list accounts")
    op_accounts = json.loads(process.stdout.decode('utf-8'))

    found_account = False
    for account in op_accounts:
        if account['shorthand'] == "my":
            found_account = True
            break

    if found_account == False:
        sys.exit("Failed, 1password account not found");

    # signin to 1password cli to get token
    process = subprocess.run('op signin --account my.1password.com --raw', shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode != 0:
        sys.exit("Failed, 1password login unsuccessful")
    TOKEN = process.stdout.decode('utf-8')

    # get key passphrases from 1password
    try:
        # get list of documents from 1password
        process = subprocess.run('op document list --format json --session ' + TOKEN, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        op_documents = json.loads(process.stdout.decode('utf-8'))

        # get ssh/gpg document uuids based on the document titles
        for document in op_documents:
            if document['title'] == "SSH private key":
                ssh_key_uuid = document['id']
            if document['title'] == "GPG private key":
                gpg_key_uuid = document['id']

        def get_passphrase_from_item(document_uuid):
            """Function to get passphrase from 1password item given its uuid"""
            process = subprocess.run('op item get ' + document_uuid + " --format json --session " + TOKEN, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            ssh_document = json.loads(process.stdout.decode('utf-8'))
            for field in ssh_document['fields']:
                if field['label'] == 'passphrase':
                    return field['value']
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
            eval_output = re.sub(".*Warning.*\n?","", eval_output) # remove lines that contain "Warning"
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
