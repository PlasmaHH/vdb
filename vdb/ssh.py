#!/usr/bin/env python3
# -*- coding: utf-8 -*-



import vdb.config
import vdb.color
import vdb.util
import vdb.command

#import vdb.cache

import gdb

import subprocess
import traceback
import select
import time
import os
import re

tmpfile = vdb.config.parameter("vdb-ssh-tempfile-name","vdb.tmpfile.{tag}.{csum}")
#csum_cmd = vdb.config.parameter("vdb-ssh-checksum-command", "sha512sum")
csum_cmd = vdb.config.parameter("vdb-ssh-checksum-command", "md5sum")
scp_cmd = vdb.config.parameter("vdb-ssh-scp-command", "scp")
scp_opts = vdb.config.parameter("vdb-ssh-scp-options", "")
gdbserver_cmd = vdb.config.parameter("vdb-ssh-gdbserver-command", "gdbserver")

csum_timeout = vdb.config.parameter("vdb-ssh-checksum-timeout-factor",4e-9)
valid_ports = vdb.config.parameter("vdb-ssh-valid-ports","5000:6000,8000:10000", on_set  = vdb.config.set_array_elements )
prompt_color = vdb.config.parameter( "vdb-ssh-colors-prompt","#ffff4f", gdb_type = vdb.config.PARAM_COLOUR )
prompt_text = vdb.config.parameter("vdb-ssh-prompt-text","vdb[{host}]> " )
scp_compression = vdb.config.parameter("vdb-ssh-scp-compression",False)

#pid_cmd = vdb.config.parameter("vdb-ssh-pid-cmd","/sbin/pidof %s")
pid_cmd = vdb.config.parameter("vdb-ssh-pid-cmd","pgrep -f %s")

"""
Plan:
    have an ssh command (and later possibly a serial command and then seperate out the common parts) that will login via
    ssh to another machine, setup all the port forwardings necessary there and attach to a gdbserver running there.

    - chose port from random range (5000-6000,8000-9000), set the range to a single port to chose a port yourself.
    - change the prompt (if activated) to something different to show that we are using a gdbserver, possibly show the
      state of the remote (if possible) with the prompt. Is target extended-remote the way to go for that?

    - using --multi we can start a gdbserver attached to nothin, but we should provide nice convenient commands to
      attach to running programs, possibly by name.

    We also need a local copy of the binary. Either we let the user provide one, or we find a mechanism to copy it over.
    We might want to check if we can use shared sockets for ssh/scp to only ever authenticate once.

    compare md5/sha checksum of remote and local binary just in case.
    What is with libraries, do we need them too or will gdbserver provide them for us somehow?



    
    - ssh host attach 4857
      to the pid 4857, error out when not found

    - ssh host attach httpd
      to the pidof(httpd) if there are multiple ones, show them and ask the user to manually specify the pid. maybe output a bit of ps axgfu context to make the choice easier?

    - ssh host filename
      all others are interpreted as filenames. do a which filename, then chose that as an argument to gdbserver and scp
      it over to a temporary storage. Check if the storage already contains the md5sum/sha to avoid copying.

    - ssh host restore
      restore a previously lost connection to an already running gdbserver.


    ssh port forwarding vs. stdout pipe. per default we should do forwarding since this allows us to re-attach to a lost
    connection ssh. Some people may not want this or it isn't working for thme (maybe port forwarding not llowed?) so we then use stdio method

    ssh idle timeout
    keep master connected ssh connections that long idle. We might also have an option to disable that master things since maybe it doesn't work for some


    we need a "cache force" mechanism where we dont do the checksum but override having a hash already so that for huge corefiles we don't need to regenerate the checksum

    check output of "info sharedlibrary" if any is missing, load them and then reset solib search path to have them loaded.

    maybe we can provide debugging so files if they exist on the target system somehow?
"""

class ssh_connection:

    def __init__( self, host, exlist = [] ):
        self.pipe = subprocess.Popen( [ "ssh", "-x", "-T", host ] + exlist, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, shell = False )
        self.timeout = 0.123456
        self.stdout_buffer = b""
        self.host = host
        self.exlist = exlist

        self.check()

        r = self.fill()
#        r = self.read()
        return
#        self.pipe.stdout = self.pipe.stdout.detach()

#        self.fill()
#        self.write("ls\n")
#        self.fill()

        try:
            self.pipe.wait(0.1)
        except:
            pass
        print("r = '%s'" % r )
        print("self.pipe = '%s'" % self.pipe )
        print("self.pipe.returncode = '%s'" % self.pipe.returncode )
#        print("len(r) = '%s'" % len(r) )

    def check( self, fail = False ):
        if( self.pipe.poll() is not None ):
            m = self.read()
            if( fail ):
                print("SSH connection to %s failed:\n%s" % (self.host,m) )
                self.detach()
#            print("m = '%s'" % m )
            return m
        return None

    def running( self ):
        pr = self.pipe.returncode
#        print("pr = '%s'" % pr )
        return ( pr is None )

    def detach( self ):
        self.pipe.terminate()
        try:
            self.wait(0.1)
        except:
            self.pipe.kill()

    def call( self, cmd ):
        if( cmd[-1] != "\n"):
            self.write(cmd+"\n")
        else:
            self.write(cmd)

    def write( self, msg ):
        self.pipe.stdin.write(msg.encode())
        self.pipe.stdin.flush()

    def fill( self, timeout = None ):
        if( len(self.stdout_buffer) != 0 ):
            return
        if( timeout is None ):
            timeout = self.timeout
        pr = select.select( [ self.pipe.stdout,self.pipe.stderr ], [], [], timeout )
        if( len(pr[0]) > 0 ):
            x = pr[0][0]
            r = x.read1(1024*1024)
            self.stdout_buffer += r
        if( timeout != 0 ):
            self.fill(0)

    def read1( self ):
        if( len(self.stdout_buffer) == 0 ):
            self.fill()
        ret = self.stdout_buffer.decode("utf-8")
        self.stdout_buffer = b""
        return ret

    def read( self ):
        r = self.read1()
        buf = r
        while( len(r) > 0 ):
            r = self.read1()
            buf += r
#            print("len(r) = '%s'" % len(r) )
#            print("r = '%s'" % r )
#        print("len(buf) = '%s'" % len(buf) )
#        print("buf = '%s'" % buf )
        return buf

def gdbserver( s, argv ):
    print("Searching for port to tunnel over ssh … ",end="")
    s.call("netstat -naput | egrep \"VERBUNDEN|LISTEN\" | cut -d':' -f2")
    s.fill(0.5)
    ports = s.read()
    ports = ports.splitlines()

    lports = subprocess.check_output(["sh","-c","netstat -npatu | egrep \"VERBUNDEN|LISTEN\" | cut -d':' -f2"])
    lports = lports.decode("utf-8")
    lports = lports.splitlines()
#    print("lports = '%s'" % lports )
    ports += lports
#    candports = set(range(6000,6020))
    candports = set(valid_ports.elements)

#    print("ports = '%s'" % ports )
    for port in ports:
        try:
            p = int(port.split()[0])
#            print("p = '%s'" % p )
            candports.remove(p)
        except:
            pass
#    print("candports = '%s'" % candports )
    if( len(candports) == 0 ):
        raise gdb.error("No suitable port found among the candidates of %s" % valid_ports.elements )
    gport = candports.pop()
    print(f"using port {gport}")
    gs = ssh_connection(s.host,[ "-L" f"{gport}:localhost:{gport}" ] )
    argv = [ f"localhost:{gport}" ] + argv
#    print("gdbserver " + " ".join(argv))
    gs.call(f"{gdbserver_cmd.value} " + " ".join(argv) )
    gs.fill(0.5)
    r=gs.read()
    print("r = '%s'" % r )
#    print(f"target remote localhost:{gport}")
#    time.sleep(2)
    print("Setting target remote…")
    gdb.execute(f"target remote localhost:{gport}")
    print("Attached to remote process. Use 'detach' to end debugging.")
    return gs


def ssh( host, ex = []):
    s = ssh_connection(host, ex )
    return s

active_ssh = None

def set_ssh( s ):
    global active_ssh
    if( active_ssh is not None ):
        active_ssh[1].detach()
        active_ssh[0].detach()
    active_ssh = s
    import vdb
    if( vdb.enabled("prompt") ):
        import vdb.prompt
        if( active_ssh is not None ):
            host = s[0].host
            vdb.prompt.set_prompt( prompt_text.value.replace("{host}",host), prompt_color.value )
        else:
            vdb.prompt.reset_prompt()

csum_cache = {
        "statistics3:/var/collectd/rrd/core.9323" : "da4a39c3032d7e675e84e8727d919683"
        }

def csum( argv ):
    key = argv[0]
    cs = argv[1]
    if( key.find(":") == -1 ):
        raise gdb.error("ssh csum <key> <csum> : the key parameter must have the form host:file but we found no ':'")
    global csum_cache
    csum_cache[key] = (cs,None)

def find_file( s, fname, tag, pid = 0, symlink=None, target = None ):
    if( s.check(True) is not None ):
        return
#    sw=vdb.cache.stopwatch()
#    sw.start()
    src = fname.replace("{pid}",str(pid))

    cachekey = f"{s.host}:{fname}"
    csum,fsize = csum_cache.get(cachekey,(None,None))
    if( fsize is None ):
        s.call("stat -L -c %s " + src)
        if( s.check(True) is not None ):
            return
        s.fill(5)
        fsize=int(s.read())
        print("fsize = '%s'" % fsize )
    if( csum is None ):
#        sw=vdb.cache.stopwatch()
#        sw.start()
#        print("src = '%s'" % src )
        s.call(csum_cmd.value + " " + src )
        print(f"Checking if {src} is already locally cached…")
        if( s.check(True) is not None ):
            return
        s.fill(csum_timeout.fvalue * fsize)
#        sw.stop()
#        print("sw.get() = '%s'" % sw.get() )
#        return
        ocsum=s.read()
        xcsum = ocsum.replace(src,"")
#        print("xcsum = '%s'" % xcsum )
        xcsum=xcsum.split()
        if( not s.running() ):
            print("BARK")
            print("s.running() = '%s'" % s.running() )
            print("s.pipe.returncode = '%s'" % s.pipe.returncode )
            print(" ".join(xcsum))
            s.check(True)
            return
        if( len(xcsum) == 0 ):
            print("Timed out getting checksum. If the file is huge or the system slow, try increasing vdb-ssh-checksum-timeout")
            return
        if( len(xcsum) != 1 ):
            print(f"Format error, expected checksum, got:\n{ocsum}")
            return
#        print("xcsum = '%s'" % xcsum )
        csum = xcsum[0]

    tmpf=tmpfile.value
    if( target is not None ):
        tmpf=target
    fn = tmpf.replace("{csum}",csum).replace("{tag}",tag)
    if( not os.path.isfile(fn) or (os.path.getsize(fn) != fsize) ):
        print(f"Copying {src} to {fn} into cache")
        scpopt=""
        if( scp_compression.value ):
            scpopt += "-C"
        print("s.exlist = '%s'" % s.exlist )
        if( len(s.exlist) != 0 ):
            scpopt += " ".join(s.exlist)
        elif( scp_opts.value ):
            scpopt += " " + scp_opts.value
#        print("scpopt = '%s'" % scpopt )
        print(f"{scp_cmd.value} {scpopt} {s.host}:{src} {fn}")
        os.system(f"{scp_cmd.value} {scpopt} {s.host}:{src} {fn}")
    else:
        print(f"Using {fn} for {src} from cache")
    if( symlink is not None and os.path.isfile(fn) ):
        try:
            os.unlink(symlink)
        except:
            pass
        os.symlink(fn,symlink)

#    sw.stop()
#    print("sw.get() = '%s'" % sw.get() )
    return fn

def run( s, argv ):
    gs = gdbserver(s,argv)
    set_ssh( (s,gs) )

def attach( s, argv ):
    pid_or_name = argv[0]
    try:
        pid = int(pid_or_name)
    except:
        print(f"Resolving pid for {pid_or_name} … ",end="")

        res=""
        try:
            s.call( pid_cmd.value % pid_or_name)
            s.fill(0.5)
            res = s.read()
        except:
            pass
        res = res.split()
        if( len(res) > 1 ):
            if( res[0].isdecimal() ):
                print("Found multiple PIDs, please chose one yourself: %s" % res )
            else:
                print("Failed to resolve PID: %s" % " ".join(res) )
            return
        if( len(res) == 0 ):
            print(f"Unable to find pid via '{pid_cmd.value}'" % pid_or_name)
#            print("s.running() = '%s'" % s.running() )
            return
#        print("res = '%s'" % res )
        pid = res[0]
        print(f"using pid {pid}")
    tfile=find_file(s,"/proc/{pid}/exe","binary",pid)
    print("tfile = '%s'" % tfile )
    gdb.execute(f"file {tfile}")
    gs = gdbserver(s,["--attach",str(pid)])
    set_ssh( (s,gs) )

def copy_libraries( s, libset, libdir, cwd ):
    for lib in libset :
        dn=os.path.dirname(f"{libdir}/{lib}")
#        ddn=os.path.dirname(f"{libdir}/usr/lib/debug/{lib}")
        os.makedirs(dn,exist_ok=True)
#        os.makedirs(ddn,exist_ok=True)

        try:
            find_file(s,lib,"lib",symlink=f"{libdir}/{lib}",target=f"{cwd}/{libdir}/lib.{{csum}}.so")
            find_file(s,"/usr/lib/debug/"+lib+".debug","lib",symlink=f"{libdir}/{lib}.debug",target=f"{cwd}/{libdir}/lib.{{csum}}.so.debug")
        except Exception as e:
            print("e = '%s'" % e )


def core( s, argv ):
#    print("argv = '%s'" % argv )
    corefile=argv[0]
    binary=None
    if( len(argv) > 1 ):
        binary=argv[1]
    if( s.check(True) is not None ):
        return


#    cf="/home/core/core.25211_ftree_1556626851_11_1000_100"
#    cf="vdb.tmpfile.core.359f81f00f853a554163d133e4bff4ed"
    print(f"Searching for corefile {corefile} on host {s.host}…")
    cf=find_file(s,corefile,"core")
    if( cf is None ):
        print(f"Could not find corefile {corefile} on remote host")
        s.detach()
        return

    if( binary is None ):
        psargs=subprocess.check_output(["sh","-c",f"eu-readelf -n {cf} | grep psargs"]).decode("utf-8")

        binary=psargs.split("psargs:")[1].split()[0]
        print(f"Binary {binary} created corefile, trying to get it…")
    else:
        print(f"Binary {binary} overrides the one from the corefile")

    bf=find_file(s,binary,"binary")

    if( bf is None ):
        print("Failed to find the binary, core file would be useless without it")
        return

    print("Checking which shared objects were loaded…")
    # method 1, get eu-readelf to output whats in the corefile
    libnotes=subprocess.check_output(["sh","-c",f"eu-readelf -n {cf} | grep / | grep -v '(deleted)' "])
    notere=re.compile("[0-9a-fA-F]*-[0-9a-fA-F]*\s*[0-9a-fA-F]*\s*[0-9]*\s*(.*)")
    libset=set()
    for note in libnotes.decode().splitlines():
#        print("note = '%s'" % note )
        m = notere.search(note)
#        print("m = '%s'" % m )
        if( m is not None ):
            libset.add(m.group(1))
#            print("note = '%s'" % note )
#            print("m.group(1) = '%s'" % m.group(1) )

    if( len(libset) == 0 ):
        print("Core file did not contain that information, trying to guess")
        s.call(f"ldd {binary}")
        s.fill(0.5)
        ldd=s.read().splitlines()
#        print("ldd = '%s'" % ldd )
        for lib in ldd:
#            print("lib = '%s'" % lib )
            if( lib.find("=>") >= 0 ):
                lib=lib.split("=>")[1].split()[0]
            else:
                lib=lib.split()[0]
#            print("lib = '%s'" % lib )
            if( lib.find("/") >= 0 ):
                libset.add(lib)
#    print("libset = '%s'" % libset )
    libdir=bf+".lib"
    if( len(libset) == 0 ):
        print("Could not determine loaded shared objects, maybe its a static binary…")
    else:
        print(f"Creating temporary library directory {libdir}…")
        os.makedirs(libdir,exist_ok=True)


    cwd=os.getcwd()
    print("Copying library files over…")
    copy_libraries(s,libset,libdir,cwd)
    print("Telling gdb to search for libraries only in our cache…")
    gdb.execute(f"add-auto-load-safe-path {cwd}/{libdir}")
    gdb.execute(f"set solib-absolute-prefix {cwd}/{libdir}")
    print("Loading binary and core file…")
    gdb.execute(f"file {bf}")
    gdb.execute(f"core {cf}")
    slibs=gdb.execute("info sharedlibrary",False,True).splitlines()
    xlibset = set()
    for slib in slibs:
        slib=slib.split()
        if( slib[0] == "No" ):
            print("Still missing library " + slib[1])
            xlibset.add(slib[1])
    if( len(xlibset) > 0 ):
        copy_libraries(s,xlibset,libdir,cwd)
        gdb.execute("set solib-search-path .")
        

def usage( ):
    print("""Usage:
  ssh [user@]host [ssh options] <subcommand> <parameter>

  Available subcommands are:

  - core        Loads the specified core file and tries to copy over all dependencies
  - attach      Attaches to the specified process (either by name or pid)
  - run         Starts a program within gdbservers control on the remote

  The [ssh options] are being used for issuing ssh commands to the specified host, the most common use probably being to
  specify a jumphost via -o proxyjump=somehost

  All (automatic) scp commands will also use this parameter. If you however set the scp-options option to something,
  then this will be used instead. Note that due to the ssh connection to the host still being open, this might still
  work without the jumphost parameter when you use master sockets.
    """)

def call_ssh( argv ):
#    print("argv = '%s'" % argv )

    if( len(argv) == 0 ):
        usage()
        return
    host = argv[0]
    cmd = argv[1]
    moreargv = argv[2:]

    extrassh = []

    while( cmd not in ["attach","core","run" ] ):
        extrassh.append(cmd)
        argv = argv[1:]
        cmd = argv[1]
        moreargv = argv[2:]
#    print("extrassh = '%s'" % extrassh )
#    print("host = '%s'" % host )
#    print("cmd = '%s'" % cmd )
#    print("moreargv = '%s'" % moreargv )

    if( len(argv) == 3 and host == "csum" ):
        csum( argv[1:] )
        return

    if( cmd == "attach" ):
        s = ssh(host, extrassh)
        attach( s, moreargv )
    elif( cmd == "run" ):
        s = ssh(host, extrassh)
        run( s, moreargv )
    elif( cmd == "core" ):
        s = ssh(host, extrassh)
        try:
            core( s, moreargv )
        except BrokenPipeError as e:
            print("ssh connection failed: %s" % e )
            print(s.read())
        finally:
            s.detach()
    else:
        print("%s is not a valid ssh subcommand" % cmd)

def remove_ssh( ev ):
    set_ssh( None )

gdb.events.exited.connect( remove_ssh )

class cmd_ssh (vdb.command.command):
    """Type ssh to get the real help"""

    def __init__ (self):
        super (cmd_ssh, self).__init__ ("ssh", gdb.COMMAND_DATA, gdb.COMPLETE_EXPRESSION)
        self.dont_repeat()

    def do_invoke (self, argv):
        try:

#            import cProfile
#            cProfile.runctx("call_ssh(argv)",globals(),locals())
            call_ssh(argv)
        except:
            traceback.print_exc()
            raise
            pass

cmd_ssh()




#gdb.events.inferior_deleted.connect( evtest )

# vim: tabstop=4 shiftwidth=4 expandtab ft=python
