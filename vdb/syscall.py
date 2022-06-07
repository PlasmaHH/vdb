#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import vdb.register

import gdb

syscalls = {
        "amd64" :
            {
                "arch_prctl"     : ([("code","int"),("unsigned long*","arg")],[]),
                "brk"            : ([("void*","addr")],[]),
                "exit"           : ([("int","error_code")],[]),
                "exit_group"     : ([("int","error_code")],[]),
                "futex"          : ( [( "uint32_t*","uaddr"),( "int", "futex_op"),("uint32_t","val") ], 
                                     [ [("timespec*","timeout"),("uint32_t","val2")],("uint32_t*","uaddr2"),("uint32_t","val3") ] ),
                "mmap"           : ([("void*","addr"),("size_t","len"),("int","prot"),("int","flags"),("int","fd"),("int","offset")],[]),
                "openat"         : ([("int","fd"),("char*","filename"),("int","flags"),("umode_t","mode")],[]),
                "read"           : ([("int","fd"),("char*","buf"),("size_t","count")],[]),
                "readv"          : ([("int","fd"),("iovec*","iov"),("int","iovcnt")],[]),
                "rt_sigprocmask" : ([("int","how"),("kernel_sigset_t*","set"),("kernel_sigset_t*","oldset"),("size_t","sigsetsize")],[]),
                "tgkill"         : ([ ("pid_t","tgid"),("pid_t","tid"),("int","sig")],[]),
                "write"          : ([("int","fd"),("char*","buf"),("size_t","count")],[]),
                "writev"         : ([("int","fd"),("iovec*","iov"),("int","iovcnt")],[]),


"io_setup": ([("unsigned","nr_reqs"),("aio_context_t*","ctx")],[]),
"io_destroy": ([("aio_context_t","ctx")],[]),
"io_submit": ([("aio_context_t",""),("long",""),("struct iocb**","")],[]),
"io_cancel": ([("aio_context_t","ctx_id"),("struct iocb*","iocb"),("struct io_event*","result")],[]),
"io_getevents": ([("aio_context_t","ctx_id"),("long","min_nr"),("long","nr"),("struct io_event*","events"),("struct __kernel_timespec*","timeout")],[]),
"io_getevents_time32": ([("__u32","ctx_id"),("__s32","min_nr"),("__s32","nr"),("struct io_event*","events"),("struct old_timespec32*","timeout")],[]),
"io_pgetevents": ([("aio_context_t","ctx_id"),("long","min_nr"),("long","nr"),("struct io_event*","events"),("struct __kernel_timespec*","timeout"),("const struct __aio_sigset*","sig")],[]),
"io_pgetevents_time32": ([("aio_context_t","ctx_id"),("long","min_nr"),("long","nr"),("struct io_event*","events"),("struct old_timespec32*","timeout"),("const struct __aio_sigset*","sig")],[]),
"io_uring_setup": ([("u32","entries"),("struct io_uring_params*","p")],[]),
"io_uring_enter": ([("unsigned int","fd"),("u32","to_submit"),("u32","min_complete"),("u32","flags"),("const void*","argp"),("size_t","argsz")],[]),
"io_uring_register": ([("unsigned int","fd"),("unsigned int","op"),("void*","arg"),("unsigned int","nr_args")],[]),
"setxattr": ([("const char*","path"),("const char*","name"),("const void*","value"),("size_t","size"),("int","flags")],[]),
"lsetxattr": ([("const char*","path"),("const char*","name"),("const void*","value"),("size_t","size"),("int","flags")],[]),
"fsetxattr": ([("int","fd"),("const char*","name"),("const void*","value"),("size_t","size"),("int","flags")],[]),
"getxattr": ([("const char*","path"),("const char*","name"),("void*","value"),("size_t","size")],[]),
"lgetxattr": ([("const char*","path"),("const char*","name"),("void*","value"),("size_t","size")],[]),
"fgetxattr": ([("int","fd"),("const char*","name"),("void*","value"),("size_t","size")],[]),
"listxattr": ([("const char*","path"),("char*","list"),("size_t","size")],[]),
"llistxattr": ([("const char*","path"),("char*","list"),("size_t","size")],[]),
"flistxattr": ([("int","fd"),("char*","list"),("size_t","size")],[]),
"removexattr": ([("const char*","path"),("const char*","name")],[]),
"lremovexattr": ([("const char*","path"),("const char*","name")],[]),
"fremovexattr": ([("int","fd"),("const char*","name")],[]),
"getcwd": ([("char*","buf"),("unsigned long","size")],[]),
"lookup_dcookie": ([("u64","cookie64"),("char*","buf"),("size_t","len")],[]),
"eventfd2": ([("unsigned int","count"),("int","flags")],[]),
"epoll_create1": ([("int","flags")],[]),
"epoll_ctl": ([("int","epfd"),("int","op"),("int","fd"),("struct epoll_event*","event")],[]),
"epoll_pwait": ([("int","epfd"),("struct epoll_event*","events"),("int","maxevents"),("int","timeout"),("const sigset_t*","sigmask"),("size_t","sigsetsize")],[]),
"epoll_pwait2": ([("int","epfd"),("struct epoll_event*","events"),("int","maxevents"),("const struct __kernel_timespec*","timeout"),("const sigset_t*","sigmask"),("size_t","sigsetsize")],[]),
"dup": ([("unsigned int","fildes")],[]),
"dup3": ([("unsigned int","oldfd"),("unsigned int","newfd"),("int","flags")],[]),
"fcntl": ([("unsigned int","fd"),("unsigned int","cmd"),("unsigned long","arg")],[]),
"fcntl64": ([("unsigned int","fd"),("unsigned int","cmd"),("unsigned long","arg")],[]),
"inotify_init1": ([("int","flags")],[]),
"inotify_add_watch": ([("int","fd"),("const char*","path"),("u32","mask")],[]),
"inotify_rm_watch": ([("int","fd"),("__s32","wd")],[]),
"ioctl": ([("unsigned int","fd"),("unsigned int","cmd"),("unsigned long","arg")],[]),
"ioprio_set": ([("int","which"),("int","who"),("int","ioprio")],[]),
"ioprio_get": ([("int","which"),("int","who")],[]),
"flock": ([("unsigned int","fd"),("unsigned int","cmd")],[]),
"mknodat": ([("int","dfd"),("const char*","filename"),("umode_t","mode"),("unsigned","dev")],[]),
"mkdirat": ([("int","dfd"),("const char*","pathname"),("umode_t","mode")],[]),
"unlinkat": ([("int","dfd"),("const char*","pathname"),("int","flag")],[]),
"symlinkat": ([("const char*","oldname"),("int","newdfd"),("const char*","newname")],[]),
"linkat": ([("int","olddfd"),("const char*","oldname"),("int","newdfd"),("const char*","newname"),("int","flags")],[]),
"renameat": ([("int","olddfd"),("const char*","oldname"),("int","newdfd"),("const char*","newname")],[]),
"umount": ([("char*","name"),("int","flags")],[]),
"mount": ([("char*","dev_name"),("char*","dir_name"),("char*","type"),("unsigned long","flags"),("void*","data")],[]),
"pivot_root": ([("const char*","new_root"),("const char*","put_old")],[]),
"statfs": ([("const char*","path"),("struct statfs*","buf")],[]),
"statfs64": ([("const char*","path"),("size_t","sz"),("struct statfs64*","buf")],[]),
"fstatfs": ([("unsigned int","fd"),("struct statfs*","buf")],[]),
"fstatfs64": ([("unsigned int","fd"),("size_t","sz"),("struct statfs64*","buf")],[]),
"truncate": ([("const char*","path"),("long","length")],[]),
"ftruncate": ([("unsigned int","fd"),("unsigned long","length")],[]),
"truncate64": ([("const char*","path"),("loff_t","length")],[]),
"ftruncate64": ([("unsigned int","fd"),("loff_t","length")],[]),
"fallocate": ([("int","fd"),("int","mode"),("loff_t","offset"),("loff_t","len")],[]),
"faccessat": ([("int","dfd"),("const char*","filename"),("int","mode")],[]),
"faccessat2": ([("int","dfd"),("const char*","filename"),("int","mode"),("int","flags")],[]),
"chdir": ([("const char*","filename")],[]),
"fchdir": ([("unsigned int","fd")],[]),
"chroot": ([("const char*","filename")],[]),
"fchmod": ([("unsigned int","fd"),("umode_t","mode")],[]),
"fchmodat": ([("int","dfd"),("const char*","filename"),("umode_t","mode")],[]),
"fchownat": ([("int","dfd"),("const char*","filename"),("uid_t","user"),("gid_t","group"),("int","flag")],[]),
"fchown": ([("unsigned int","fd"),("uid_t","user"),("gid_t","group")],[]),
"openat2": ([("int","dfd"),("const char*","filename"),("struct open_how*","how"),("size_t","size")],[]),
"close": ([("unsigned int","fd")],[]),
"close_range": ([("unsigned int","fd"),("unsigned int","max_fd"),("unsigned int","flags")],[]),
"vhangup": ([("void","")],[]),
"pipe2": ([("int*","fildes"),("int","flags")],[]),
"quotactl": ([("unsigned int","cmd"),("const char*","special"),("qid_t","id"),("void*","addr")],[]),
"quotactl_fd": ([("unsigned int","fd"),("unsigned int","cmd"),("qid_t","id"),("void*","addr")],[]),
"getdents64": ([("unsigned int","fd"),("struct linux_dirent64*","dirent"),("unsigned int","count")],[]),
"llseek": ([("unsigned int","fd"),("unsigned long","offset_high"),("unsigned long","offset_low"),("loff_t*","result"),("unsigned int","whence")],[]),
"lseek": ([("unsigned int","fd"),("off_t","offset"),("unsigned int","whence")],[]),
"pread64": ([("unsigned int","fd"),("char*","buf"),("size_t","count"),("loff_t","pos")],[]),
"pwrite64": ([("unsigned int","fd"),("const char*","buf"),("size_t","count"),("loff_t","pos")],[]),
"preadv": ([("unsigned long","fd"),("const struct iovec*","vec"),("unsigned long","vlen"),("unsigned long","pos_l"),("unsigned long","pos_h")],[]),
"pwritev": ([("unsigned long","fd"),("const struct iovec*","vec"),("unsigned long","vlen"),("unsigned long","pos_l"),("unsigned long","pos_h")],[]),
"sendfile64": ([("int","out_fd"),("int","in_fd"),("loff_t*","offset"),("size_t","count")],[]),
"pselect6": ([("int",""),("fd_set*",""),("fd_set*",""),("fd_set*",""),("struct __kernel_timespec*",""),("void*","")],[]),
"pselect6_time32": ([("int",""),("fd_set*",""),("fd_set*",""),("fd_set*",""),("struct","old_timespec32*"),("void*","")],[]),
"ppoll": ([("struct pollfd*",""),("unsigned","int"),("struct __kernel_timespec*",""),("const sigset_t*",""),("size_t","")],[]),
"ppoll_time32": ([("struct pollfd*",""),("unsigned","int"),("struct","old_timespec32*"),("const sigset_t*",""),("size_t","")],[]),
"signalfd4": ([("int","ufd"),("sigset_t*","user_mask"),("size_t","sizemask"),("int","flags")],[]),
"vmsplice": ([("int","fd"),("const struct iovec*","iov"),("unsigned long","nr_segs"),("unsigned int","flags")],[]),
"splice": ([("int","fd_in"),("loff_t*","off_in"),("int","fd_out"),("loff_t*","off_out"),("size_t","len"),("unsigned int","flags")],[]),
"tee": ([("int","fdin"),("int","fdout"),("size_t","len"),("unsigned int","flags")],[]),
"readlinkat": ([("int","dfd"),("const char*","path"),("char*","buf"),("int","bufsiz")],[]),
"newfstatat": ([("int","dfd"),("const char*","filename"),("struct stat*","statbuf"),("int","flag")],[]),
"newfstat": ([("unsigned int","fd"),("struct stat*","statbuf")],[]),
"fstat64": ([("unsigned long","fd"),("struct stat64*","statbuf")],[]),
"fstatat64": ([("int","dfd"),("const char*","filename"),("struct stat64*","statbuf"),("int","flag")],[]),
"sync": ([("void","")],[]),
"fsync": ([("unsigned int","fd")],[]),
"fdatasync": ([("unsigned int","fd")],[]),
"sync_file_range2": ([("int","fd"),("unsigned int","flags"),("loff_t","offset"),("loff_t","nbytes")],[]),
"sync_file_range": ([("int","fd"),("loff_t","offset"),("loff_t","nbytes"),("unsigned int","flags")],[]),
"timerfd_create": ([("int","clockid"),("int","flags")],[]),
"timerfd_settime": ([("int","ufd"),("int","flags"),("const struct __kernel_itimerspec*","utmr"),("struct __kernel_itimerspec*","otmr")],[]),
"timerfd_gettime": ([("int","ufd"),("struct __kernel_itimerspec*","otmr")],[]),
"timerfd_gettime32": ([("int","ufd"),("struct old_itimerspec32*","otmr")],[]),
"timerfd_settime32": ([("int","ufd"),("int","flags"),("const struct old_itimerspec32*","utmr"),("struct old_itimerspec32*","otmr")],[]),
"utimensat": ([("int","dfd"),("const char*","filename"),("struct __kernel_timespec*","utimes"),("int","flags")],[]),
"utimensat_time32": ([("unsigned int","dfd"),("const char*","filename"),("struct old_timespec32*","t"),("int","flags")],[]),
"acct": ([("const char*","name")],[]),
"capget": ([("cap_user_header_t","header"),("cap_user_data_t","dataptr")],[]),
"capset": ([("cap_user_header_t","header"),("const cap_user_data_t","data")],[]),
"personality": ([("unsigned int","personality")],[]),

"waitid": ([("int","which"),("pid_t","pid"),("struct siginfo*","infop"),("int","options"),("struct rusage*","ru")],[]),
"set_tid_address": ([("int*","tidptr")],[]),
"unshare": ([("unsigned long","unshare_flags")],[]),
"futex_time32": ([("u32*","uaddr"),("int","op"),("u32","val"),("const struct old_timespec32*","utime"),("u32*","uaddr2"),("u32","val3")],[]),
"get_robust_list": ([("int","pid"),("struct robust_list_head**","head_ptr"),("size_t*","len_ptr")],[]),
"set_robust_list": ([("struct robust_list_head*","head"),("size_t","len")],[]),
"nanosleep": ([("struct __kernel_timespec*","rqtp"),("struct __kernel_timespec*","rmtp")],[]),
"nanosleep_time32": ([("struct old_timespec32*","rqtp"),("struct old_timespec32*","rmtp")],[]),
"getitimer": ([("int","which"),("struct __kernel_old_itimerval*","value")],[]),
"setitimer": ([("int","which"),("struct __kernel_old_itimerval*","value"),("struct __kernel_old_itimerval*","ovalue")],[]),
"kexec_load": ([("unsigned long","entry"),("unsigned long","nr_segments"),("struct kexec_segment*","segments"),("unsigned long","flags")],[]),
"init_module": ([("void*","umod"),("unsigned long","len"),("const char*","uargs")],[]),
"delete_module": ([("const char*","name_user"),("unsigned int","flags")],[]),
"timer_create": ([("clockid_t","which_clock"),("struct sigevent*","timer_event_spec"),("timer_t*","created_timer_id")],[]),
"timer_gettime": ([("timer_t","timer_id"),("struct __kernel_itimerspec*","setting")],[]),
"timer_getoverrun": ([("timer_t","timer_id")],[]),
"timer_settime": ([("timer_t","timer_id"),("int","flags"),("const struct __kernel_itimerspec*","new_setting"),("struct __kernel_itimerspec*","old_setting")],[]),
"timer_delete": ([("timer_t","timer_id")],[]),
"clock_settime": ([("clockid_t","which_clock"),("const struct __kernel_timespec*","tp")],[]),
"clock_gettime": ([("clockid_t","which_clock"),("struct __kernel_timespec*","tp")],[]),
"clock_getres": ([("clockid_t","which_clock"),("struct __kernel_timespec*","tp")],[]),
"clock_nanosleep": ([("clockid_t","which_clock"),("int","flags"),("const struct __kernel_timespec*","rqtp"),("struct __kernel_timespec*","rmtp")],[]),
"timer_gettime32": ([("timer_t","timer_id"),("struct old_itimerspec32*","setting")],[]),
"timer_settime32": ([("timer_t","timer_id"),("int","flags"),("struct old_itimerspec32*","new"),("struct old_itimerspec32*","old")],[]),
"clock_settime32": ([("clockid_t","which_clock"),("struct old_timespec32*","tp")],[]),
"clock_gettime32": ([("clockid_t","which_clock"),("struct old_timespec32*","tp")],[]),
"clock_getres_time32": ([("clockid_t","which_clock"),("struct old_timespec32*","tp")],[]),
"clock_nanosleep_time32": ([("clockid_t","which_clock"),("int","flags"),("struct old_timespec32*","rqtp"),("struct old_timespec32*","rmtp")],[]),
"syslog": ([("int","type"),("char*","buf"),("int","len")],[]),
"ptrace": ([("long","request"),("long","pid"),("unsigned long","addr"),("unsigned long","data")],[]),
"sched_setparam": ([("pid_t","pid"),("struct sched_param*","param")],[]),
"sched_setscheduler": ([("pid_t","pid"),("int","policy"),("struct sched_param*","param")],[]),
"sched_getscheduler": ([("pid_t","pid")],[]),
"sched_getparam": ([("pid_t","pid"),("struct sched_param*","param")],[]),
"sched_setaffinity": ([("pid_t","pid"),("unsigned int","len"),("unsigned long*","user_mask_ptr")],[]),
"sched_getaffinity": ([("pid_t","pid"),("unsigned int","len"),("unsigned long*","user_mask_ptr")],[]),
"sched_yield": ([("void","")],[]),
"sched_get_priority_max": ([("int","policy")],[]),
"sched_get_priority_min": ([("int","policy")],[]),
"sched_rr_get_interval": ([("pid_t","pid"),("struct __kernel_timespec*","interval")],[]),
"sched_rr_get_interval_time32": ([("pid_t","pid"),("struct old_timespec32*","interval")],[]),
"restart_syscall": ([("void","")],[]),
"kill": ([("pid_t","pid"),("int","sig")],[]),
"tkill": ([("pid_t","pid"),("int","sig")],[]),
"sigaltstack": ([("const struct sigaltstack*","uss"),("struct sigaltstack*","uoss")],[]),
"rt_sigsuspend": ([("sigset_t*","unewset"),("size_t","sigsetsize")],[]),
"rt_sigaction": ([("int",""),("const struct sigaction*",""),("struct sigaction*",""),("size_t","")],[]),
"rt_sigpending": ([("sigset_t*","set"),("size_t","sigsetsize")],[]),
"rt_sigtimedwait": ([("const sigset_t*","uthese"),("siginfo_t*","uinfo"),("const struct __kernel_timespec*","uts"),("size_t","sigsetsize")],[]),
"rt_sigtimedwait_time32": ([("const sigset_t*","uthese"),("siginfo_t*","uinfo"),("const struct old_timespec32*","uts"),("size_t","sigsetsize")],[]),
"rt_sigqueueinfo": ([("pid_t","pid"),("int","sig"),("siginfo_t*","uinfo")],[]),
"setpriority": ([("int","which"),("int","who"),("int","niceval")],[]),
"getpriority": ([("int","which"),("int","who")],[]),
"reboot": ([("int","magic1"),("int","magic2"),("unsigned int","cmd"),("void*","arg")],[]),
"setregid": ([("gid_t","rgid"),("gid_t","egid")],[]),
"setgid": ([("gid_t","gid")],[]),
"setreuid": ([("uid_t","ruid"),("uid_t","euid")],[]),
"setuid": ([("uid_t","uid")],[]),
"setresuid": ([("uid_t","ruid"),("uid_t","euid"),("uid_t","suid")],[]),
"getresuid": ([("uid_t*","ruid"),("uid_t*","euid"),("uid_t*","suid")],[]),
"setresgid": ([("gid_t","rgid"),("gid_t","egid"),("gid_t","sgid")],[]),
"getresgid": ([("gid_t*","rgid"),("gid_t*","egid"),("gid_t*","sgid")],[]),
"setfsuid": ([("uid_t","uid")],[]),
"setfsgid": ([("gid_t","gid")],[]),
"times": ([("struct tms*","tbuf")],[]),
"setpgid": ([("pid_t","pid"),("pid_t","pgid")],[]),
"getpgid": ([("pid_t","pid")],[]),
"getsid": ([("pid_t","pid")],[]),
"setsid": ([("void","")],[]),
"getgroups": ([("int","gidsetsize"),("gid_t*","grouplist")],[]),
"setgroups": ([("int","gidsetsize"),("gid_t*","grouplist")],[]),
"newuname": ([("struct new_utsname*","name")],[]),
"sethostname": ([("char*","name"),("int","len")],[]),
"setdomainname": ([("char*","name"),("int","len")],[]),
"getrlimit": ([("unsigned int","resource"),("struct rlimit*","rlim")],[]),
"setrlimit": ([("unsigned int","resource"),("struct rlimit*","rlim")],[]),
"getrusage": ([("int","who"),("struct rusage*","ru")],[]),
"umask": ([("int","mask")],[]),
"prctl": ([("int","option"),("unsigned long","arg2"),("unsigned long","arg3"),("unsigned long","arg4"),("unsigned long","arg5")],[]),
"getcpu": ([("unsigned*","cpu"),("unsigned*","node"),("struct getcpu_cache*","cache")],[]),
"gettimeofday": ([("struct __kernel_old_timeval*","tv"),("struct timezone*","tz")],[]),
"settimeofday": ([("struct __kernel_old_timeval*","tv"),("struct timezone*","tz")],[]),
"adjtimex": ([("struct __kernel_timex*","txc_p")],[]),
"adjtimex_time32": ([("struct old_timex32*","txc_p")],[]),
"getpid": ([("void","")],[]),
"getppid": ([("void","")],[]),
"getuid": ([("void","")],[]),
"geteuid": ([("void","")],[]),
"getgid": ([("void","")],[]),
"getegid": ([("void","")],[]),
"gettid": ([("void","")],[]),
"sysinfo": ([("struct sysinfo*","info")],[]),
"mq_open": ([("const char*","name"),("int","oflag"),("umode_t","mode"),("struct mq_attr*","attr")],[]),
"mq_unlink": ([("const char*","name")],[]),
"mq_timedsend": ([("mqd_t","mqdes"),("const char*","msg_ptr"),("size_t","msg_len"),("unsigned int","msg_prio"),("const struct __kernel_timespec*","abs_timeout")],[]),
"mq_timedreceive": ([("mqd_t","mqdes"),("char*","msg_ptr"),("size_t","msg_len"),("unsigned int*","msg_prio"),("const struct __kernel_timespec*","abs_timeout")],[]),
"mq_notify": ([("mqd_t","mqdes"),("const struct sigevent*","notification")],[]),
"mq_getsetattr": ([("mqd_t","mqdes"),("const struct mq_attr*","mqstat"),("struct mq_attr*","omqstat")],[]),
"mq_timedreceive_time32": ([("mqd_t","mqdes"),("char*","u_msg_ptr"),("unsigned int","msg_len"),("unsigned int*","u_msg_prio"),("const struct old_timespec32*","u_abs_timeout")],[]),
"mq_timedsend_time32": ([("mqd_t","mqdes"),("const char*","u_msg_ptr"),("unsigned int","msg_len"),("unsigned int","msg_prio"),("const struct old_timespec32*","u_abs_timeout")],[]),
"msgget": ([("key_t","key"),("int","msgflg")],[]),
"old_msgctl": ([("int","msqid"),("int","cmd"),("struct msqid_ds*","buf")],[]),
"msgctl": ([("int","msqid"),("int","cmd"),("struct msqid_ds*","buf")],[]),
"msgrcv": ([("int","msqid"),("struct msgbuf*","msgp"),("size_t","msgsz"),("long","msgtyp"),("int","msgflg")],[]),
"msgsnd": ([("int","msqid"),("struct msgbuf*","msgp"),("size_t","msgsz"),("int","msgflg")],[]),
"semget": ([("key_t","key"),("int","nsems"),("int","semflg")],[]),
"semctl": ([("int","semid"),("int","semnum"),("int","cmd"),("unsigned long","arg")],[]),
"old_semctl": ([("int","semid"),("int","semnum"),("int","cmd"),("unsigned long","arg")],[]),
"semtimedop": ([("int","semid"),("struct sembuf*","sops"),("unsigned","nsops"),("const struct __kernel_timespec*","timeout")],[]),
"semtimedop_time32": ([("int","semid"),("struct sembuf*","sops"),("unsigned","nsops"),("const struct old_timespec32*","timeout")],[]),
"semop": ([("int","semid"),("struct sembuf*","sops"),("unsigned","nsops")],[]),
"shmget": ([("key_t","key"),("size_t","size"),("int","flag")],[]),
"old_shmctl": ([("int","shmid"),("int","cmd"),("struct shmid_ds*","buf")],[]),
"shmctl": ([("int","shmid"),("int","cmd"),("struct shmid_ds*","buf")],[]),
"shmat": ([("int","shmid"),("char*","shmaddr"),("int","shmflg")],[]),
"shmdt": ([("char*","shmaddr")],[]),
"socket": ([("int",""),("int",""),("int","")],[]),
"socketpair": ([("int",""),("int",""),("int",""),("int*","")],[]),
"bind": ([("int",""),("struct sockaddr*",""),("int","")],[]),
"listen": ([("int",""),("int","")],[]),
"accept": ([("int",""),("struct sockaddr*",""),("int*","")],[]),
"connect": ([("int",""),("struct sockaddr*",""),("int","")],[]),
"getsockname": ([("int",""),("struct sockaddr*",""),("int*","")],[]),
"getpeername": ([("int",""),("struct sockaddr*",""),("int*","")],[]),
"sendto": ([("int",""),("void*",""),("size_t",""),("unsigned",""),("struct sockaddr*",""),("int","")],[]),
"recvfrom": ([("int",""),("void*",""),("size_t",""),("unsigned",""),("struct sockaddr*",""),("int*","")],[]),
"setsockopt": ([("int","fd"),("int","level"),("int","optname"),("char*","optval"),("int","optlen")],[]),
"getsockopt": ([("int","fd"),("int","level"),("int","optname"),("char*","optval"),("int*","optlen")],[]),
"shutdown": ([("int",""),("int","")],[]),
"sendmsg": ([("int","fd"),("struct user_msghdr*","msg"),("unsigned","flags")],[]),
"recvmsg": ([("int","fd"),("struct user_msghdr*","msg"),("unsigned","flags")],[]),
"readahead": ([("int","fd"),("loff_t","offset"),("size_t","count")],[]),
"munmap": ([("unsigned long","addr"),("size_t","len")],[]),
"mremap": ([("unsigned long","addr"),("unsigned long","old_len"),("unsigned long","new_len"),("unsigned long","flags"),("unsigned long","new_addr")],[]),
"add_key": ([("const char*","_type"),("const char*","_description"),("const void*","_payload"),("size_t","plen"),("key_serial_t","destringid")],[]),
"request_key": ([("const char*","_type"),("const char*","_description"),("const char*","_callout_info"),("key_serial_t","destringid")],[]),
"keyctl": ([("int","cmd"),("unsigned long","arg2"),("unsigned long","arg3"),("unsigned long","arg4"),("unsigned long","arg5")],[]),
"clone": ([("unsigned","long"),("unsigned","long"),("int*",""),("unsigned","long"),("int*","")],[]),
"clone": ([("unsigned","long"),("unsigned","long"),("int",""),("int*",""),("int*",""),("unsigned","long")],[]),
"clone": ([("unsigned","long"),("unsigned","long"),("int*",""),("int*",""),("unsigned","long")],[]),
"clone3": ([("struct clone_args*","uargs"),("size_t","size")],[]),
"execve": ([("const char*","filename"),("const char*","const* argv"),("const char*","const* envp")],[]),
"fadvise64_64": ([("int","fd"),("loff_t","offset"),("loff_t","len"),("int","advice")],[]),
"swapon": ([("const char*","specialfile"),("int","swap_flags")],[]),
"swapoff": ([("const char*","specialfile")],[]),
"mprotect": ([("unsigned long","start"),("size_t","len"),("unsigned long","prot")],[]),
"msync": ([("unsigned long","start"),("size_t","len"),("int","flags")],[]),
"mlock": ([("unsigned long","start"),("size_t","len")],[]),
"munlock": ([("unsigned long","start"),("size_t","len")],[]),
"mlockall": ([("int","flags")],[]),
"munlockall": ([("void","")],[]),
"mincore": ([("unsigned long","start"),("size_t","len"),("unsigned char*","vec")],[]),
"madvise": ([("unsigned long","start"),("size_t","len"),("int","behavior")],[]),
"process_madvise": ([("int","pidfd"),("const struct iovec*","vec"),("size_t","vlen"),("int","behavior"),("unsigned int","flags")],[]),
"remap_file_pages": ([("unsigned long","start"),("unsigned long","size"),("unsigned long","prot"),("unsigned long","pgoff"),("unsigned long","flags")],[]),
"mbind": ([("unsigned long","start"),("unsigned long","len"),("unsigned long","mode"),("const unsigned long*","nmask"),("unsigned long","maxnode"),("unsigned","flags")],[]),
"get_mempolicy": ([("int*","policy"),("unsigned long*","nmask"),("unsigned long","maxnode"),("unsigned long","addr"),("unsigned long","flags")],[]),
"set_mempolicy": ([("int","mode"),("const unsigned long*","nmask"),("unsigned long","maxnode")],[]),
"migrate_pages": ([("pid_t","pid"),("unsigned long","maxnode"),("const unsigned long*","from"),("const unsigned long*","to")],[]),
"move_pages": ([("pid_t","pid"),("unsigned long","nr_pages"),("const void**","pages"),("const int*","nodes"),("int*","status"),("int","flags")],[]),
"rt_tgsigqueueinfo": ([("pid_t","tgid"),("pid_t","pid"),("int","sig"),("siginfo_t*","uinfo")],[]),
"perf_event_open": ([("struct perf_event_attr*","attr_uptr"),("pid_t","pid"),("int","cpu"),("int","group_fd"),("unsigned long","flags")],[]),
"accept4": ([("int",""),("struct sockaddr*",""),("int*",""),("int","")],[]),
"recvmmsg": ([("int","fd"),("struct mmsghdr*","msg"),("unsigned int","vlen"),("unsigned","flags"),("struct __kernel_timespec*","timeout")],[]),
"recvmmsg_time32": ([("int","fd"),("struct mmsghdr*","msg"),("unsigned int","vlen"),("unsigned","flags"),("struct old_timespec32*","timeout")],[]),
"wait4": ([("pid_t","pid"),("int*","stat_addr"),("int","options"),("struct rusage*","ru")],[]),
"prlimit64": ([("pid_t","pid"),("unsigned int","resource"),("const struct rlimit64*","new_rlim"),("struct rlimit64*","old_rlim")],[]),
"fanotify_init": ([("unsigned int","flags"),("unsigned int","event_f_flags")],[]),
"fanotify_mark": ([("int","fanotify_fd"),("unsigned int","flags"),("u64","mask"),("int","fd"),("const char*","pathname")],[]),
"name_to_handle_at": ([("int","dfd"),("const char*","name"),("struct file_handle*","handle"),("int*","mnt_id"),("int","flag")],[]),
"open_by_handle_at": ([("int","mountdirfd"),("struct file_handle*","handle"),("int","flags")],[]),
"clock_adjtime": ([("clockid_t","which_clock"),("struct __kernel_timex*","tx")],[]),
"clock_adjtime32": ([("clockid_t","which_clock"),("struct old_timex32*","tx")],[]),
"syncfs": ([("int","fd")],[]),
"setns": ([("int","fd"),("int","nstype")],[]),
"pidfd_open": ([("pid_t","pid"),("unsigned int","flags")],[]),
"sendmmsg": ([("int","fd"),("struct mmsghdr*","msg"),("unsigned int","vlen"),("unsigned","flags")],[]),
"process_vm_readv": ([("pid_t","pid"),("const struct iovec*","lvec"),("unsigned long","liovcnt"),("const struct iovec*","rvec"),("unsigned long","riovcnt"),("unsigned long","flags")],[]),
"process_vm_writev": ([("pid_t","pid"),("const struct iovec*","lvec"),("unsigned long","liovcnt"),("const struct iovec*","rvec"),("unsigned long","riovcnt"),("unsigned long","flags")],[]),
"kcmp": ([("pid_t","pid1"),("pid_t","pid2"),("int","type"),("unsigned long","idx1"),("unsigned long","idx2")],[]),
"finit_module": ([("int","fd"),("const char*","uargs"),("int","flags")],[]),
"sched_setattr": ([("pid_t","pid"),("struct sched_attr*","attr"),("unsigned int","flags")],[]),
"sched_getattr": ([("pid_t","pid"),("struct sched_attr*","attr"),("unsigned int","size"),("unsigned int","flags")],[]),
"renameat2": ([("int","olddfd"),("const char*","oldname"),("int","newdfd"),("const char*","newname"),("unsigned int","flags")],[]),
"seccomp": ([("unsigned int","op"),("unsigned int","flags"),("void*","uargs")],[]),
"getrandom": ([("char*","buf"),("size_t","count"),("unsigned int","flags")],[]),
"memfd_create": ([("const char*","uname_ptr"),("unsigned int","flags")],[]),
"bpf": ([("int","cmd"),("union bpf_attr*","attr"),("unsigned int","size")],[]),
"execveat": ([("int","dfd"),("const char*","filename"),("const char*","const* argv"),("const char*","const* envp"),("int","flags")],[]),
"userfaultfd": ([("int","flags")],[]),
"membarrier": ([("int","cmd"),("unsigned int","flags"),("int","cpu_id")],[]),
"mlock2": ([("unsigned long","start"),("size_t","len"),("int","flags")],[]),
"copy_file_range": ([("int","fd_in"),("loff_t*","off_in"),("int","fd_out"),("loff_t*","off_out"),("size_t","len"),("unsigned int","flags")],[]),
"preadv2": ([("unsigned long","fd"),("const struct iovec*","vec"),("unsigned long","vlen"),("unsigned long","pos_l"),("unsigned long","pos_h"),("rwf_t","flags")],[]),
"pwritev2": ([("unsigned long","fd"),("const struct iovec*","vec"),("unsigned long","vlen"),("unsigned long","pos_l"),("unsigned long","pos_h"),("rwf_t","flags")],[]),
"pkey_mprotect": ([("unsigned long","start"),("size_t","len"),("unsigned long","prot"),("int","pkey")],[]),
"pkey_alloc": ([("unsigned long","flags"),("unsigned long","init_val")],[]),
"pkey_free": ([("int","pkey")],[]),
"statx": ([("int","dfd"),("const char*","path"),("unsigned","flags"),("unsigned","mask"),("struct statx*","buffer")],[]),
"rseq": ([("struct rseq*","rseq"),("uint32_t","rseq_len"),("int","flags"),("uint32_t","sig")],[]),
"open_tree": ([("int","dfd"),("const char*","path"),("unsigned","flags")],[]),
"move_mount": ([("int","from_dfd"),("const char*","from_path"),("int","to_dfd"),("const char*","to_path"),("unsigned int","ms_flags")],[]),
"mount_setattr": ([("int","dfd"),("const char*","path"),("unsigned int","flags"),("struct mount_attr*","uattr"),("size_t","usize")],[]),
"fsopen": ([("const char*","fs_name"),("unsigned int","flags")],[]),
"fsconfig": ([("int","fs_fd"),("unsigned int","cmd"),("const char*","key"),("const void*","value"),("int","aux")],[]),
"fsmount": ([("int","fs_fd"),("unsigned int","flags"),("unsigned int","ms_flags")],[]),
"fspick": ([("int","dfd"),("const char*","path"),("unsigned int","flags")],[]),
"pidfd_send_signal": ([("int","pidfd"),("int","sig"),("siginfo_t*","info"),("unsigned int","flags")],[]),
"pidfd_getfd": ([("int","pidfd"),("int","fd"),("unsigned int","flags")],[]),
"landlock_create_ruleset": ([("const struct landlock_ruleset_attr*","attr"),("size_t","size"),("__u32","flags")],[]),
"landlock_add_rule": ([("int","ruleset_fd"),("enum landlock_rule_type","rule_type"),("const void*","rule_attr"),("__u32","flags")],[]),
"landlock_restrict_self": ([("int","ruleset_fd"),("__u32","flags")],[]),
"memfd_secret": ([("unsigned int","flags")],[]),
"ioperm": ([("unsigned long","from"),("unsigned long","num"),("int","on")],[]),
"pciconfig_read": ([("unsigned long","bus"),("unsigned long","dfn"),("unsigned long","off"),("unsigned long","len"),("void*","buf")],[]),
"pciconfig_write": ([("unsigned long","bus"),("unsigned long","dfn"),("unsigned long","off"),("unsigned long","len"),("void*","buf")],[]),
"pciconfig_iobase": ([("long","which"),("unsigned long","bus"),("unsigned long","devfn")],[]),
"spu_run": ([("int","fd"),("__u32*","unpc"),("__u32*","ustatus")],[]),
"spu_create": ([("const char*","name"),("unsigned int","flags"),("umode_t","mode"),("int","fd")],[]),
"open": ([("const char*","filename"),("int","flags"),("umode_t","mode")],[]),
"link": ([("const char*","oldname"),("const char*","newname")],[]),
"unlink": ([("const char*","pathname")],[]),
"mknod": ([("const char*","filename"),("umode_t","mode"),("unsigned","dev")],[]),
"chmod": ([("const char*","filename"),("umode_t","mode")],[]),
"chown": ([("const char*","filename"),("uid_t","user"),("gid_t","group")],[]),
"mkdir": ([("const char*","pathname"),("umode_t","mode")],[]),
"rmdir": ([("const char*","pathname")],[]),
"lchown": ([("const char*","filename"),("uid_t","user"),("gid_t","group")],[]),
"access": ([("const char*","filename"),("int","mode")],[]),
"rename": ([("const char*","oldname"),("const char*","newname")],[]),
"symlink": ([("const char*","old"),("const char*","new")],[]),
"stat64": ([("const char*","filename"),("struct stat64*","statbuf")],[]),
"lstat64": ([("const char*","filename"),("struct stat64*","statbuf")],[]),
"pipe": ([("int*","fildes")],[]),
"dup2": ([("unsigned int","oldfd"),("unsigned int","newfd")],[]),
"epoll_create": ([("int","size")],[]),
"inotify_init": ([("void","")],[]),
"eventfd": ([("unsigned int","count")],[]),
"signalfd": ([("int","ufd"),("sigset_t*","user_mask"),("size_t","sizemask")],[]),
"sendfile": ([("int","out_fd"),("int","in_fd"),("off_t*","offset"),("size_t","count")],[]),
"newstat": ([("const char*","filename"),("struct stat*","statbuf")],[]),
"newlstat": ([("const char*","filename"),("struct stat*","statbuf")],[]),
"fadvise64": ([("int","fd"),("loff_t","offset"),("size_t","len"),("int","advice")],[]),
"alarm": ([("unsigned int","seconds")],[]),
"getpgrp": ([("void","")],[]),
"pause": ([("void","")],[]),
"time": ([("__kernel_old_time_t*","tloc")],[]),
"time32": ([("old_time32_t*","tloc")],[]),
"utime": ([("char*","filename"),("struct utimbuf*","times")],[]),
"utimes": ([("char*","filename"),("struct __kernel_old_timeval*","utimes")],[]),
"futimesat": ([("int","dfd"),("const char*","filename"),("struct __kernel_old_timeval*","utimes")],[]),
"futimesat_time32": ([("unsigned int","dfd"),("const char*","filename"),("struct old_timeval32*","t")],[]),
"utime32": ([("const char*","filename"),("struct old_utimbuf32*","t")],[]),
"utimes_time32": ([("const char*","filename"),("struct old_timeval32*","t")],[]),
"creat": ([("const char*","pathname"),("umode_t","mode")],[]),
"getdents": ([("unsigned int","fd"),("struct linux_dirent*","dirent"),("unsigned int","count")],[]),
"select": ([("int","n"),("fd_set*","inp"),("fd_set*","outp"),("fd_set*","exp"),("struct __kernel_old_timeval*","tvp")],[]),
"poll": ([("struct pollfd*","ufds"),("unsigned int","nfds"),("int","timeout")],[]),
"epoll_wait": ([("int","epfd"),("struct epoll_event*","events"),("int","maxevents"),("int","timeout")],[]),
"ustat": ([("unsigned","dev"),("struct ustat*","ubuf")],[]),
"vfork": ([("void","")],[]),
"recv": ([("int",""),("void*",""),("size_t",""),("unsigned","")],[]),
"send": ([("int",""),("void*",""),("size_t",""),("unsigned","")],[]),
"bdflush": ([("int","func"),("long","data")],[]),
"oldumount": ([("char*","name")],[]),
"uselib": ([("const char*","library")],[]),
"sysfs": ([("int","option"),("unsigned long","arg1"),("unsigned long","arg2")],[]),
"fork": ([("void","")],[]),
"stime": ([("__kernel_old_time_t*","tptr")],[]),
"stime32": ([("old_time32_t*","tptr")],[]),
"sigpending": ([("old_sigset_t*","uset")],[]),
"sigprocmask": ([("int","how"),("old_sigset_t*","set"),("old_sigset_t*","oset")],[]),
"sigsuspend": ([("old_sigset_t","mask")],[]),
"sigsuspend": ([("int","unused1"),("int","unused2"),("old_sigset_t","mask")],[]),
"sigaction": ([("int",""),("const struct old_sigaction*",""),("struct old_sigaction*","")],[]),
"sgetmask": ([("void","")],[]),
"ssetmask": ([("int","newmask")],[]),
"signal": ([("int","sig"),("__sighandler_t","handler")],[]),
"nice": ([("int","increment")],[]),
"kexec_file_load": ([("int","kernel_fd"),("int","initrd_fd"),("unsigned long","cmdline_len"),("const char*","cmdline_ptr"),("unsigned long","flags")],[]),
"waitpid": ([("pid_t","pid"),("int*","stat_addr"),("int","options")],[]),
"chown16": ([("const char*","filename"),("old_uid_t","user"),("old_gid_t","group")],[]),
"lchown16": ([("const char*","filename"),("old_uid_t","user"),("old_gid_t","group")],[]),
"fchown16": ([("unsigned int","fd"),("old_uid_t","user"),("old_gid_t","group")],[]),
"setregid16": ([("old_gid_t","rgid"),("old_gid_t","egid")],[]),
"setgid16": ([("old_gid_t","gid")],[]),
"setreuid16": ([("old_uid_t","ruid"),("old_uid_t","euid")],[]),
"setuid16": ([("old_uid_t","uid")],[]),
"setresuid16": ([("old_uid_t","ruid"),("old_uid_t","euid"),("old_uid_t","suid")],[]),
"getresuid16": ([("old_uid_t*","ruid"),("old_uid_t*","euid"),("old_uid_t*","suid")],[]),
"setresgid16": ([("old_gid_t","rgid"),("old_gid_t","egid"),("old_gid_t","sgid")],[]),
"getresgid16": ([("old_gid_t*","rgid"),("old_gid_t*","egid"),("old_gid_t*","sgid")],[]),
"setfsuid16": ([("old_uid_t","uid")],[]),
"setfsgid16": ([("old_gid_t","gid")],[]),
"getgroups16": ([("int","gidsetsize"),("old_gid_t*","grouplist")],[]),
"setgroups16": ([("int","gidsetsize"),("old_gid_t*","grouplist")],[]),
"getuid16": ([("void","")],[]),
"geteuid16": ([("void","")],[]),
"getgid16": ([("void","")],[]),
"getegid16": ([("void","")],[]),
"socketcall": ([("int","call"),("unsigned long*","args")],[]),
"stat": ([("const char*","filename"),("struct __old_kernel_stat*","statbuf")],[]),
"lstat": ([("const char*","filename"),("struct __old_kernel_stat*","statbuf")],[]),
"fstat": ([("unsigned int","fd"),("struct __old_kernel_stat*","statbuf")],[]),
"readlink": ([("const char*","path"),("char*","buf"),("int","bufsiz")],[]),
"old_select": ([("struct sel_arg_struct*","arg")],[]),
"old_readdir": ([("unsigned","int"),("struct","old_linux_dirent*"),("unsigned","int")],[]),
"gethostname": ([("char*","name"),("int","len")],[]),
"uname": ([("struct old_utsname*","")],[]),
"olduname": ([("struct old_utsname*","")],[]),
"old_getrlimit": ([("unsigned int","resource"),("struct rlimit*","rlim")],[]),
"ipc": ([("unsigned int","call"),("int","first"),("unsigned long","second"),("unsigned long","third"),("void*","ptr"),("long","fifth")],[]),
"mmap_pgoff": ([("unsigned long","addr"),("unsigned long","len"),("unsigned long","prot"),("unsigned long","flags"),("unsigned long","fd"),("unsigned long","pgoff")],[]),
"old_mmap": ([("struct mmap_arg_struct*","arg")],[]),



 }
        }

enum_maps = {
        "futex:futex_op" :
            {
                0   : "FUTEX_WAIT",                 1   : "FUTEX_WAKE",                 2   : "FUTEX_FD",               3   : "FUTEX_REQUEUE",
                128 : "FUTEX_WAIT_PRIVATE",         129 : "FUTEX_WAKE_PRIVATE",                                         131 : "FUTEX_REQUEUE_PRIVATE",

                4   : "FUTEX_CMP_REQUEUE",          5   : "FUTEX_WAKE_OP",              6   : "FUTEX_LOCK_PI",          7   : "FUTEX_UNLOCK_PI",
                132 : "FUTEX_CMP_REQUEUE_PRIVATE", 133 : "FUTEX_WAKE_OP_PRIVATE",       134 : "FUTEX_LOCK_PI_PRIVATE",  135 : "FUTEX_UNLOCK_PI_PRIVATE",

                8   : "FUTEX_TRYLOCK_PI",           9   : "FUTEX_WAIT_BITSET",          10  : "FUTEX_WAKE_BITSET",          11  : "FUTEX_WAIT_REQUEUE_PI",
                136 : "FUTEX_TRYLOCK_PI_PRIVATE",   137 : "FUTEX_WAIT_BITSET_PRIVATE",  138 : "FUTEX_WAKE_BITSET_PRIVATE",  139 : "FUTEX_WAIT_REQUEUE_PI_PRIVATE",

                12  : "FUTEX_CMP_REQUEUE_PI",
                140 : "FUTEX_CMP_REQUEUE_PI_PRIVATE",

                256 : "FUTEX_CLOCK_REALTIME"
            },
        "rt_sigprocmask:how" :
            {
                0   : "SIG_BLOCK", 1 : "SIG_UNBLOCK", 2 : "SIG_SETMASK"
            },
        "openat:fd" :
            {
                -100: "AT_FDCWD"
            }
        }

flag_maps = {
        "openat:flags" : [
            ("O_ACCMODE",0o00000003),
            ("O_RDONLY",0o00000000),
            ("O_WRONLY",0o00000001),
            ("O_RDWR",0o00000002),
            ("O_CREAT",0o00000100),
            ("O_EXCL",0o00000200),
            ("O_NOCTTY",0o00000400),
            ("O_TRUNC",0o00001000),
            ("O_APPEND",0o00002000),
            ("O_NONBLOCK",0o00004000),
            ("O_DSYNC",0o00010000),
            ("FASYNC",0o00020000),
            ("O_DIRECT",0o00040000),
            ("O_LARGEFILE",0o00100000),
            ("O_DIRECTORY",0o00200000),
            ("O_NOFOLLOW",0o00400000),
            ("O_NOATIME",0o01000000),
            ("O_CLOEXEC",0o02000000),
            ("__O_SYNC",0o04000000),
            ("O_PATH",0o010000000),
            ("__O_TMPFILE",0o020000000),
            ]
        }

format_options = {
        "openat:flags" : lambda x : oct(x).replace("o","")
        }


syscall_conventions = {
        "amd64" : {
            "number" : "rax",
            "ret0" : "rax",
            "ret1" : "rdx",
            "args" : [ "rdi", "rsi", "rdx", "r10", "r8", "r9" ],
            "clobber" : [ "rax", "rcx" ]
            }
        }

syscall_db = {}

class syscall_parameter:
    def __init__( self ):
        self.names = []
        self.types = []
        self.register = None

def reg( r, rd, qm = "?", frame = None ):
    ret,r = rd.get(r,None)
    q = ""
    if( ret is None ):
        try:
            if( frame is not None ):
                ret = frame.read_register(r)
            if( ret is None or ret.is_optimized_out ):
                ret = vdb.register.read(r)
        except:
            return (None,True)
        q = qm
    return (str(ret),q)

def param_str( syscall, val, ptype, pname, register, questionable ):
    if( val is not None ):
        try:
            val = gdb.parse_and_eval(f"({ptype})({val})")
        except:
            # assume the type is not known, we fall back to void* then
            val = gdb.parse_and_eval(f"(void*)({val})")

        emap = enum_maps.get(f"{syscall}:{pname}",None)
        fm = flag_maps.get(f"{syscall}:{pname}",None)
        fo = format_options.get(f"{syscall}:{pname}",None)

        if( emap is not None ):
            ename = emap.get(vdb.util.mint(val),None)
            if( ename is not None ):
                val = f"{val}({ename})"
        elif( fm is not None ):
            fs = ""
            for f in fm:
                val = int(val)
                if( val & f[1] ):
                    fs += f[0] + "|"
            if( len(fs) > 0 ):
                fs = fs[:-1]
            if( fo is not None ):
                val = fo(val)
            val = f"{val}({fs})"
        elif( fo is not None ):
            val = fo(val)
    else:
        val = "???"

    ret = f"{pname}[{register}] = {val}"
    ret += questionable
#    if( questionable ):
#        ret += "?"
    return ret

class syscall:

    def __init__(self, nr, name):
        self.nr = nr
        self.name = name
        self.parameters = []
        self.optional_paramters = []
        self.clobbers = []

    def to_str( self, registers, qm = "?", frame = None ):

        ret = f"{self.name}[{self.nr}]( "
        for p in self.parameters:
            rval,q = reg(p.register,registers,qm,frame)
            ret += param_str(self.name,rval,p.types[0],p.names[0],p.register, q)
            ret += ","
        ret = ret[:-1]

        if( len(self.optional_paramters) > 0 ):
            if( len(self.parameters) > 0 ):
                ret += ","
            for o in self.optional_paramters:
                rval,q = reg(o.register,registers,qm,frame)
                ret += param_str(self.name,rval,o.types[0],o.names[0],o.register,q)
                ret += ","
            ret = ret[:-1]

        ret += ")"
        return ret

    def clobber( self, registers ):
        ret = registers
        for reg in self.clobbers:
            ret.remove(reg)
            alt = vdb.register.altname(reg)
            if( alt is not None ):
                ret.pop(alt,None)
        return ret

def get( nr ):
    return syscall_db.get(nr,None)

def gather_params( sarch, plist, cnt = 0 ):
    ret = []

    args = syscall_conventions[sarch][("args")]
    for polyparam in plist:
        sp = syscall_parameter()
        ret.append(sp)
        if( len(args) > cnt ):
            sp.register = args[cnt]

#        print("cnt = '%s'" % (cnt,) )
#        print("sp.register = '%s'" % (sp.register,) )

        cnt += 1
        if( type(polyparam) == list ):
            for ptype,pname in polyparam:
                sp.names.append(pname)
                sp.types.append(ptype)
        else:
#            print("polyparam = '%s'" % (polyparam,) )
            ptype,pname = polyparam
            sp.names.append(pname)
            sp.types.append(ptype)
            if( len(pname) > 0 and pname[-1]  == "*" ):
                print("pname = '%s'" % (pname,) )
#            print("ptype = '%s'" % (ptype,) )
#            print("pname = '%s'" % (pname,) )
    return ret

def parse_xml( fn = None ):
    # XXX depending on the architecture change the path and relead the information
    sarch = "amd64"
    if( fn is None ):
        fn = f"/usr/share/gdb/syscalls/{sarch}-linux.xml"
    calldict = syscalls[sarch]

    try:
        from defusedxml.ElementTree import parse
    except:
        from xml.etree.ElementTree import parse
    et = parse(fn)

    global syscall_db
    for s in et.iter("syscall"):
        name = s.attrib[("name")]
        nr = s.attrib[("number")]

        paramlist,optparamlist = calldict.get(name,(None,None) )
        sc = syscall(nr,name)
#        print("name = '%s'" % (name,) )
        if( paramlist is not None ):
            sc.parameters = gather_params(sarch,paramlist)
            sc.optional_paramters = gather_params(sarch,optparamlist,len(sc.parameters))
        sc.clobbers = syscall_conventions[sarch][("clobber")]
#        print(f"{nr} => {sc.name}")
        syscall_db[int(nr)] = sc



try:
    parse_xml()
except:
    pass
# vim: tabstop=4 shiftwidth=4 expandtab ft=python
