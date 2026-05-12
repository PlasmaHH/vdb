# Hardfault module

The hardfault module provides assistance in diagnosing ARM Cortex-M hard faults. When a Cortex-M microcontroller
encounters a fatal error (memory access violation, bus error, usage fault, etc.), it enters the HardFault handler.
This module helps analyze the cause of the fault by examining the relevant fault status registers.

## Overview

ARM Cortex-M processors have a Nested Vectored Interrupt Controller (NVIC) with several fault handlers:
- **MemManage** - Memory management faults (memory protection violations)
- **BusFault** - Bus errors (invalid bus accesses)
- **UsageFault** - Usage errors (undefined instructions, invalid state, etc.)

When any of these faults occur and are not handled by their specific handler, they escalate to the HardFault handler.
The module reads the various System Control Block (SCB) registers to determine the root cause.

## Commands

### `hardfault`

Analyzes the current hard fault state by reading and interpreting the fault status registers. This is the primary
command of the module and is invoked without parameters.

```
(gdb) hardfault
Hard Fault interesting registers:
Analyzing hard fault reasons and conditions...
Usage Fault Reason: [UNDEFINSTR] Undefined instruction
Bus Fault Reason: [IBUSERR] Instruction bus error,[BFARVALID] BFAR valid
BUS Fault while trying to access memory at 0x00000000
MMFAR not valid
Possible recovered pc 0x8005a3c from msp @0x20001000
#0  HardFault_Handler () at main.c:42
#1  0x08005a3c in main ()
```

## Fault Register Analysis

The module reads and interprets the following registers from the SCB (System Control Block):

### UFSR (Usage Fault Status Register)

| Bit | Flag | Description |
|-----|------|-------------|
| 16 | UNDEFINSTR | Undefined instruction access |
| 17 | INVSTATE | Invalid PSR/execution state |
| 18 | INVPC | Invalid PC loaded |
| 19 | NOCP | Coprocessor error |
| 20 | STKOF | Stack overflow on exception entry |
| 23 | UNALIGNED | Unaligned access error |
| 24 | DIVBYZERO | Divide by zero |

### BFSR (Bus Fault Status Register)

| Bit | Flag | Description |
|-----|------|-------------|
| 1 | IBUSERR | Instruction bus error |
| 2 | PRECISERR | Precise data bus error |
| 3 | IMPRECISERR | Imprecise data bus error |
| 4 | UNSTKERR | Unstacking bus error |
| 5 | STKERR | Stacking bus error |
| 6 | LSPERR | Lazy state preservation error |
| 15 | BFARVALID | BFAR value is valid |

### MMFSR (MemManage Fault Status Register)

| Bit | Flag | Description |
|-----|------|-------------|
| 0 | IACCVIOL | Instruction access violation |
| 1 | DACCVIOL | Data access violation |
| 3 | MUNSTKERR | MemManage unstacking error |
| 4 | MSTKERR | MemManage stacking error |
| 5 | MLSPERR | MemManage lazy state preservation error |
| 7 | MMARVALID | MMFAR value is valid |

## Stack Pointer Recovery

After a hard fault, the module attempts to recover the original Program Counter by examining the stack frames pointed to
by both the Main Stack Pointer (MSP) and Process Stack Pointer (PSP). On Cortex-M, the exception frame on the stack
contains the saved registers in a specific order (R0, R1, R2, R3, R12, LR, PC, xPSR), and the module reads the PC
value (the 7th word on the stack).

## Requirements

- ARM Cortex-M target
- SVD files loaded for the target (the module uses `reg/M` to access memory-mapped SCB registers)
- The SVD must define `SCB.UFSR`, `SCB.BFSR`, `SCB.MMFSR`, `SCB.HFSR`, `SCB.BFAR`, and `SCB.MMFAR`

## Workflow

1. Target enters HardFault handler
2. Run `hardfault` to analyze fault registers
3. Review the fault reasons to identify the root cause
4. Check the recovered PC value to find the instruction that caused the fault
5. Use `bt` (backtrace) for additional context

## Common Causes

- **NULL pointer dereference** - BusFault with BFAR = 0x0
- **Stack overflow** - UsageFault with STKOF flag
- **Undefined instruction** - UsageFault with UNDEFINSTR (e.g., executing data as code)
- **Divide by zero** - UsageFault with DIVBYZERO (if enabled in CCR)
- **Memory protection violation** - MemManage fault (if MPU is configured)

## Limitations

- Requires SVD files to be properly loaded for the target microcontroller
- Start/stop/status/dash subcommands are currently placeholders
- Does not automatically detect hard faults; must be invoked manually when stopped in the fault handler
- Stack pointer recovery assumes a standard Cortex-M exception frame layout