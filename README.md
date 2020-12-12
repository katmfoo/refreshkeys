# refreshkeys

Keychain wrapper that retrieves ssh/gpg key passphrases from 1password

### Installation

* Depends on 1password cli, jq, and keychain
* Make sure gpg agent is configured to use tty pinentry (add the following to `~/.gnupg/gpg-agent.conf`
```
pinentry-program /usr/bin/pinentry-tty
```
* Install with `pip install git+https://github.com/pricheal/refreshkeys.git`
* Add the following to your `.bashrc`:
```
eval $(refreshkeys --eval --if-needed)
```
