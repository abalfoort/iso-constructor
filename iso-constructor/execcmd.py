#!/usr/bin/env python3

import subprocess


# Class to execute a command and return the output in an array
class ExecCmd(object):

    def __init__(self, loggerObject=None):
        self.log = loggerObject

    def run(self, command, realTime=True, returnAsList=True, workingDir=None):
        lstOut = []
        msg = "Run command: {}".format(command)
        print(msg)
        if self.log:
            self.log.write(msg, 'execcmd.run', 'debug')

        p = subprocess.Popen(command, shell=True, bufsize=0, stdout=subprocess.PIPE, universal_newlines=True, cwd=workingDir)
        for line in p.stdout:
            # Strip the line, also from null spaces (strip() only strips white spaces)
            line = line.strip().strip('\n').strip('\0')
            lstOut.append(line)
            if realTime:
                print(line) if not self.log else self.log.write(line, 'execcmd.run', 'info')
        p.stdout.close()
        return_code = p.wait()
        if return_code:
            print("Command '{cmd}' returned non-zero exit status: {code}".format(cmd=command, code=return_code))

        return lstOut if returnAsList else "\n".join(lstOut)
