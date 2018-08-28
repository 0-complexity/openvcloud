#!/usr/bin/env/python
import subprocess
import cStringIO
import re
import sys
import time

password = sys.argv[1]
cores = int(sys.argv[2])
runtime = int(sys.argv[3])
start = time.time()
results = ""
stderr = ""
exitcodes = list()
output = "/home/cloudscalers/test_res.output"
while True:
    now = time.time()
    if now - start > runtime:
        break
    cwd = "/home/cloudscalers/UnixBench"
    passwordin = cStringIO.StringIO("%s\n" % password)
    proc = subprocess.Popen(
        args=[
            "echo %s | sudo -S ./Run -c %s -t 1 2>&1 | tee -a %s"
            % (password, cores, output)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        shell=True,
    )
    results += proc.stdout.read()
    stderr += proc.stderr.read()
    proc.wait()
    exitcodes.append(str(proc.returncode))

with open("/home/cloudscalers/test_res.txt.stdexitcodes", "w") as file:
    file.write("\n".join(exitcodes))

match = re.finditer(r"System Benchmarks Index Score\s+([\d.]+)", results)
matches = [float(m.group(1)) for m in match]
if len(matches) != 0:
    print(sum(matches) / len(matches))
else:
    print("0")
