#taken from https://gist.github.com/1711614


def bicommand(command, showoutput=False, read_bytes=1):
    import subprocess
    import select
    import sys

    if not showoutput in [True, False]:
        raise "showoutput takes a boolean argument only"

    pipe = subprocess.Popen(command, shell=True,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    output = ""
    while True:
        to_read, _, _ = select.select([pipe.stdout, pipe.stderr], [], [], 0.1)
        if len(to_read) == 0:
            continue

        eof = True
        for stream in to_read:
            line = stream.read(read_bytes)
            if line != "":
                eof = False
            output += line
            if showoutput is True:
                sys.stdout.write(line)
                pass

        if eof is True:
            break

        pass

    if output[-1:] == '\n':
        output = output[:-1]
        pass

    status = pipe.wait()

    return status, output
