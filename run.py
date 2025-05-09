#!/usr/bin/env python3

import subprocess
import sys
import os
import tempfile
import shutil

def run_command(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cwd, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}")
        print(e.output)
        sys.exit(1)

def java_compile(java_file, bin_dir, classpath=None):
    javac_cmd = ['javac', '-d', bin_dir]
    if classpath:
        javac_cmd += ['-cp', classpath]
    javac_cmd.append(java_file)
    run_command(javac_cmd)

def detect_false_positive(java_file_path):
    root_dir = os.getcwd()
    target_method = "test"
    evosuite_jar = os.path.join(root_dir, 'tools', 'evosuite.jar')
    fp_jar = os.path.join(root_dir, 'tools', 'fp.jar')

    # Derive class info
    rel_path = os.path.relpath(java_file_path, root_dir)
    classname_path = rel_path.replace("/", ".").replace(".java", "")
    class_name = os.path.basename(java_file_path).replace(".java", "")

    # Temporary directories for bin/src
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, 'src')
        bin_dir = os.path.join(tmpdir, 'bin')
        os.makedirs(src_dir)
        os.makedirs(bin_dir)

        tmp_java_path = os.path.join(src_dir, os.path.basename(java_file_path))
        shutil.copy(java_file_path, tmp_java_path)

        # Compile the class
        java_compile(tmp_java_path, bin_dir)

        # Get line list from fp.jar
        line_list = run_command(['java', '-jar', fp_jar, tmp_java_path, target_method]).strip()

        # Recompile after instrumentation (assumed in-place modification by fp.jar)
        java_compile(tmp_java_path, bin_dir)

        # Run EvoSuite
        evo_cmd = [
            'java', '-jar', evosuite_jar,
            '-generateTests',
            '-Dsearch_budget=60',
            '-Dcriterion=branch',
            '-Dassertions=false',
            '-Dstrategy=onebranch',
            '-Dtest_comments=true',
            f"-Djunit_suffix=_{target_method}_Test",
            f"-Dline_list={line_list}",
            f"-Dtarget_method_prefix={target_method}",
            '-projectCP', bin_dir,
            '-class', classname_path
        ]
        output = run_command(evo_cmd)

        # Determine result
        if "Generated 0" not in output and "Resulting test suite" in output:
            print("False Positive Detected!")
        elif "Resulting test suite" in output:
            print("No False Positive Detected!")
        else:
            print("EvoSuite did not produce a valid test suite.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: run.py <path_to_java_file>")
        sys.exit(1)

    detect_false_positive(sys.argv[1])

