#!/usr/bin/env python2.6

"""
bsub_eprover 0.1

Usage: bsub_eprover.py <stratfile> ...

Parse the strategy description files provided, generate corresponding
LSF batch files, and submit them to the LSF system for running. This
is, more or less, a one-off hack and not particularly configurable
except by editing the source code.

Options:

-h
   Print this help.

-v
--verbose
   Switch on verbose mode.

Copyright 2010 Stephan Schulz, schulz@eprover.org

This code is part of the support structure for the equational
theorem prover E. Visit

 http://www.eprover.org

for more information.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program ; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston,
MA  02111-1307 USA 

The original copyright holder can be contacted as

Stephan Schulz (I4)
Technische Universitaet Muenchen
Institut fuer Informatik
Boltzmannstrasse 3
Garching bei Muenchen
Germany

or via email (address above).
"""

import sys
import re
import os
import string
import getopt
import pylib_io
import pylib_db
import pylib_eprot
import pylib_erun


def test_cfg():
    global tptp_dir, eprover_dir, testrun_dir, bsub_cmd, bjobs_cmd,\
    bsub_rundir, old_job_dir, db_file
    
    tptp_dir = "/Users/schulz/EPROVER/TPTP_4.1.0_FLAT"
    """
    Where are the TPTP problem files?
    """

    eprover_dir = "/Users/schulz/SOURCES/Projects/E/PROVER"
    """
    Where is the eprover binary?
    """

    testrun_dir = "/Users/schulz/EPROVER/TESTRUNS_SERVER"
    """
    Where are spec- and protocol files?
    """

    bsub_cmd="head -2"
    """
    Name of the batch submission program (normally bsub, but we use cat
    for testing).
    """

    bjobs_cmd="cat EXAMPLE_CFG/bjobs.txt"
    """
    Command to list jobs in queue. Will be bjobs -w on the cluster.
    """

    bsub_rundir = "/tmp"
    """
    Where will E run and deposit results?
    """

    old_job_dir = "/tmp/schulz/e_jobs_done"
    """
    Where to move old result files (if any).
    """

    db_file = "EXAMPLE_CFG/bjob_db.db"
    """
    Where to store the job/run associations.
    """


def pegasus_cfg():
    global tptp_dir, eprover_dir, testrun_dir, bsub_cmd, bjobs_cmd,\
    bsub_rundir, old_job_dir, db_file
    
    tptp_dir = "/nethome/sschulz/EPROVER/TPTP_4.1.0_FLAT"
    """
    Where are the TPTP problem files?
    """

    eprover_dir = "/nethome/sschulz/bin"
    """
    Where is the eprover binary?
    """

    testrun_dir = "/nethome/sschulz/EPROVER/TESTRUNS_PEGASUS"
    """
    Where are spec- and protocol files?
    """

    bsub_cmd="bsub"
    """
    Name of the batch submission program (normally bsub, but we use cat
    for testing).
    """

    bjobs_cmd="bjobs -w"
    """
    Command to list jobs in queue. Will be bjobs -w on the cluster.
    """

    bsub_rundir = "/nethome/sschulz/RUN"
    """
    Where will E run and deposit results?
    """

    old_job_dir = "/scratch/sschulz/e_jobs_done"
    """
    Where to move old result files (if any).
    """

    db_file = "/nethome/sschulz/RUN/bjob_db.db"
    """
    Where to store the job/run associations.
    """


max_bsub_jobs = 900
"""
How many jobs are allowed at the same time.
"""

max_bsub_batch = 100
"""
How many prover runs are combined in one batch.
"""


res_complete_marker = re.compile("### Job complete ###")
"""
Result files are considered complete if they contain this string.
"""

bsub_tmplt = \
"""
#!/bin/bash
#BSUB -J %s
#BSUB -o %s.out   
#BSUB -e %s.err  
#BSUB -W 0:10   
#BSUB -q small 
#BSUB -n 1      
#
# Run serial executable on 1 cpu of one node
cd %s
env TPTP=%s %s/eprover --print-statistics --tptp3-format --resources-info %s %s
echo "### Job complete ###"
"""
"""
Template for generating bsub jobs.
"""


bsub_header_tmplt = \
"""
#!/bin/bash
#BSUB -J %s
#BSUB -o %s.out   
#BSUB -e %s.err  
#BSUB -W 0:10   
#BSUB -q small 
#BSUB -n 1      
#
# Run serial executable on 1 cpu of one node
"""
"""
Template for generating bsub job headers.
"""

bsub_job_tmplt = \
"""
echo "### Running : %s"
cd %s
env TPTP=%s %s/eprover --print-statistics --tptp3-format --resources-info %s %s
"""
"""
Template for generating bsub job entries.
"""

ejobname_re=re.compile("erun#[^ ]*.out")
"""
Regular expression matching E job names.
"""

ejob_re=re.compile("erun#[^ ]*")
"""
Regular expression matching E jobs.
"""


def bsub_submit(job):
    """
    Submit a job to bsub.
    """
    os.chdir(bsub_rundir)
    fp = os.popen(bsub_cmd, "w")
    fp.write(job)
    fp.close()


def encode_res_name(stratname, probname):
    """
    Given a strategy name and the problem name, return the job name.
    """
    return "erun#%s#%s"%(stratname, probname)

def decode_res_name(filename):
    """
    Results for a given test run are stored in a file whose name
    includes the name of the tested strategy and the name of the
    problem. This function extracts these components and returns them
    as a tuple (stratname, probname).
    """
    if filename.endswith(".err") or filename.endswith(".out"):
        filename = filename[:-4]
    
    tmp = filename.split("#")
    if len(tmp) != 3:
        return None
    return tmp[1], tmp[2]
    

def find_batch_jobs(job_db):
    """
    Find all jobs in the job queue and return them in the form of a
    set. 
    """
    res = set()
    count = 0;
    
    txt = pylib_io.run_shell_command(bjobs_cmd)
    for i in txt:
        mo = ejob_re.search(i)
        if mo:
            count = count+1
            job = mo.group()
            assoc = job_db.find_entry(job)
            if assoc:
                res.extend(assoc)
            else:
                res.add(job)

    return count,res

def bsub_gen(stratname, probname, args):
    """
    Generate a bsub specification.
    """
    jname = encode_res_name(stratname, probname)
    return bsub_tmplt%\
           (jname, jname, jname, bsub_rundir,  tptp_dir, eprover_dir,
            args, probname)


def read_res_file(filename):
    """
    Try to open and read the named file. Return the contents if
    successful and the file contains the string
    '### Job complete ###', None otherwise.
    """
    try:
        fp = pylib_io.flexopen(filename, "r")
    except IOError:
        return None
    res = fp.read()

    mo = res_complete_marker.search(res)
    if mo:
        return res
    return None


def decode_result(decoder, stratset, filename):
    """
    Parse a result file and insetr it into stratse. Return true on
    success, false otherwise.
    """
    resstr = read_res_file(filename)
    if resstr:
        sname, pname = decode_res_name(filename)
        strat = stratset.find_strat(sname)
        maxtime = strat.spec.time_limit
        res = pylib_eprot.eresult(pname+" "+decoder.encode_result(resstr,maxtime))
        if res:
            strat.add_result(res)
            return True
        return False
    else:
        return False
        

def process_complete_jobs(decoder, stratset, resdir = "", donedir=None):
    """
    Process all jobs in resdir. Store the results in stratset, move
    processed complete files to donedir (if this argument is given).
    """
    os.chdir(resdir)
    names = os.listdir(".")

    for job in names:
        if ejobname_re.match(job):
            pylib_io.verbout("Parsing "+job);
            res = decode_result(decoder, stratset, job)
            if res and donedir:
                joberr = job[:-4]+".err"
                try:
                    os.unlink(job)
                    os.unlink(joberr)
                except OSError:
                    pass


def bsub_gen_header(job):
    """
    Generate a bsub specification header.
    """
    stratname = job.strat()
    probname  = job.prob()
    jname = encode_res_name(stratname, probname)
    return bsub_header_tmplt%\
           (jname, jname, jname)


def bsub_gen_job(job):
    """
    Generate a bsub single job command.
    """
    stratname = job.strat()
    probname  = job.prob()
    args      = job.get_args()
    jname = encode_res_name(stratname, probname)
    return bsub_job_tmplt%\
           (jname, bsub_rundir,  tptp_dir, eprover_dir,
            args, probname)

             
def bsub_gen_batch(batch):
    """
    Generate a batch description for bsub to run the jobs in batch.
    """
    header = bsub_gen_header(batch[0])

    joblist = [bsub_gen_job(i) for i in batch]
    jobs = "\n".join(joblist)
    
    footer = '\necho "### Job complete ###"\n'

    return header+jobs+footer


def process_strat(name, results, running, max_jobs):
    """
    Determine the strategy base name, parse any results (individually
    and collected), determine the missing problems, and submit them
    via bsub.
    """
    strat = results.find_strat(name)

    open_jobs = []
    for job in strat.generate_jobs():
        jname = encode_res_name(job.strat(), job.prob())
        if not jname in running:
            open_jobs.append(job)

    print "Found ", len(open_jobs), " open jobs in ", name

    res = 0
    while len(open_jobs) and res < max_jobs:
        batch     = open_jobs[:max_bsub_batch]
        open_jobs = open_jobs[max_bsub_batch:]
        res = res+1
        
        job_str = bsub_gen_batch(batch)
        jname = encode_res_name(batch[0].strat(), batch[0].prob())
        print "Submitting ", jname, " with ", len(batch), " problems"
        bsub_submit(job_str)

    return res

if __name__ == '__main__':
    opts, args = getopt.gnu_getopt(sys.argv[1:], "hvpfb:j:",
                                   ["--pegasus",
                                    "--force",
                                    "--batchsize="
                                    "--jobs="])
    force_scheduling = False

    test_cfg()
    for option, optarg in opts:
        if option == "-h":
            print __doc__
            sys.exit()
        elif option == "-v":
            pylib_io.Verbose = 1
        elif option == "-p" or option == "--pegasus":
            pegasus_cfg()
        elif option == "-f" or option == "--force":
            force_scheduling = True
        elif option =="-b" or option =="--batchsize":
            max_bsub_batch = int(optarg)
        elif option =="-j" or option =="--jobs":
            max_bsub_jobs = int(optarg)
        else:
            sys.exit("Unknown option "+ option)

    try:
        os.makedirs(bsub_rundir)
        os.makedirs(old_job_dir)
    except OSError:
        pass

    job_db = pylib_db.key_db(db_file)
    results = pylib_eprot.estrat_set(testrun_dir)    
    parser = pylib_erun.e_res_parser(300, ["# Processed clauses",
                                           "# Unification attempts",
                                           "# Unification successes"])

    jobcount, scheduled = find_batch_jobs(job_db)

    print "Currently running:", jobcount

    if force_scheduling:
        scheduled = set()
        
    process_complete_jobs(parser, results, bsub_rundir, old_job_dir)
    results.sync()

    max_bsub_jobs = max_bsub_jobs - jobcount
    for name in args:
        newscheduled = process_strat(name, results, scheduled, max_bsub_jobs)
        max_bsub_jobs = max_bsub_jobs - newscheduled
        if max_bsub_jobs <= 0:
            break
