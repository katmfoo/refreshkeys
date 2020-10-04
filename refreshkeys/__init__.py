import pexpect

def main():
    print('refreshkeys script test')
    child = pexpect.spawn('ls')
    child.sendline('yahoooo')
