import distutils.spawn
import sys
import os
import json
import subprocess
import pexpect

# refreshkeys, script to refresh ssh/gpg key passphrases in keychain using 1password
# source: https://github.com/pricheal/refreshkeys

def program_installed(name: str) -> bool:
    """Returns whether or not the given program is installed on the system"""
    return distutils.spawn.find_executable(name) is not None

def main():
    """Main logic of script"""

    OP_ADDRESS = "https://my.1password.com"
    OP_EMAIL = "patrickricheal@gmail.com"

    # ensure necessary command line tools are installed
    if not program_installed('jq'): sys.exit('refreshkeys failed, jq not installed')
    if not program_installed('op'): sys.exit('refreshkeys failed, 1password cli not installed')
    if not program_installed('keychain'): sys.exit('refreshkeys failed, keychain not installed')

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
        process = subprocess.run('op signin my ' + OP_EMAIL + '--raw', shell=True, stdout=subprocess.PIPE)
    else:
        process = subprocess.run('op signin my --raw', shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if process.returncode != 0:
        sys.exit('refreshkeys failed, 1password login unsuccessful')
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

        def get_passphrase(document_uuid):
            """Function to get passphrase from 1password document given its uuid"""
            process = subprocess.run('op get item ' + document_uuid + " --session " + TOKEN, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            ssh_document = json.loads(process.stdout.decode('utf-8'))
            for section in ssh_document['details']['sections']:
                for field in section['fields']:
                    if field['t'] == 'passphrase':
                        return field['v']
            return None

        # get passphrases
        ssh_key_passphrase = get_passphrase(ssh_key_uuid)
        gpg_key_passphrase = get_passphrase(gpg_key_uuid)

        if not ssh_key_passphrase or not gpg_key_passphrase:
            raise Exception()

    except:
        sys.exit('refreshkeys failed, error retrieving passphrases from 1password')

    try:
        # clear keychain
        subprocess.run('keychain --clear --agents ssh,gpg', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # run keychain
        process = pexpect.spawn('keychain --quiet --nogui --timeout 1440 --agents ssh,gpg id_rsa 2A70B83FD3493624')

        # wait for ssh passphrase prompt
        process.expect('Enter passphrase for')
        process.sendline(ssh_key_passphrase)

        # wait for gpg passphrase prompt
        process.expect('Passphrase:')
        process.sendline(gpg_key_passphrase)

        # wait for process to complete
        process.wait()
    except:
        sys.exit('refreshkeys failed, keychain unsuccessful')

    print('refreshkeys successful')

if __name__ == "__main__":
    main()
