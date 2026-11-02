#!/usr/bin/env bash
# Reference solution. Undoes each edit and writes the expected report.
# Proves the task is solvable. Never present in the agent image.
set -euo pipefail
cd /workspace/repo
git apply --whitespace=nowarn /solution/solution.patch
mkdir -p /app
cat > /app/rca.json <<'RCA'
{
  "causes": [
    {
      "file": "/workspace/repo/arch/ARM/ARMDisassembler.c",
      "function": "DecodeVST4LN"
    },
    {
      "file": "/workspace/repo/arch/ARM/ARMMapping.c",
      "function": "ARM_add_cs_detail"
    },
    {
      "file": "/workspace/repo/arch/Mips/MipsDisassembler.c",
      "function": "DecodeBgtzGroupBranch"
    },
    {
      "file": "/workspace/repo/arch/HPPA/HPPADisassembler.c",
      "function": "fill_branch_mods"
    },
    {
      "file": "/workspace/repo/arch/TriCore/TriCoreDisassembler.c",
      "function": "DecodeSRCInstruction"
    },
    {
      "file": "/workspace/repo/arch/AArch64/AArch64Disassembler.c",
      "function": "DecodeVecShiftLImm"
    },
    {
      "file": "/workspace/repo/arch/BPF/BPFDisassembler.c",
      "function": "op2insn_alu"
    },
    {
      "file": "/workspace/repo/arch/M680X/M680XInstPrinter.c",
      "function": "M680X_printInst"
    },
    {
      "file": "/workspace/repo/arch/X86/X86InstPrinterCommon.c",
      "function": "printSSEAVXCC"
    },
    {
      "file": "/workspace/repo/arch/M68K/M68KInstPrinter.c",
      "function": "extended_to_double"
    },
    {
      "file": "/workspace/repo/arch/M68K/M68KDisassembler.c",
      "function": "dcf_coproc_ldst"
    },
    {
      "file": "/workspace/repo/arch/X86/X86DisassemblerDecoder.c",
      "function": "readPrefixes"
    },
    {
      "file": "/workspace/repo/arch/Sparc/SparcInstPrinter.c",
      "function": "Sparc_LLVM_getRegisterName"
    },
    {
      "file": "/workspace/repo/arch/TMS320C64x/TMS320C64xInstPrinter.c",
      "function": "printAliasInstruction"
    },
    {
      "file": "/workspace/repo/arch/RISCV/RISCVInstPrinter.c",
      "function": "printBranchOperand"
    },
    {
      "file": "/workspace/repo/arch/AArch64/AArch64InstPrinter.c",
      "function": "printMatrixTileList"
    },
    {
      "file": "/workspace/repo/arch/ARM/ARMInstPrinter.c",
      "function": "printMSRMaskOperand"
    },
    {
      "file": "/workspace/repo/MCInst.c",
      "function": "MCOperand_isImm"
    },
    {
      "file": "/workspace/repo/arch/PowerPC/PPCInstPrinter.c",
      "function": "printInst"
    },
    {
      "file": "/workspace/repo/arch/ARC/ARCDisassembler.c",
      "function": "readInstruction48"
    },
    {
      "file": "/workspace/repo/arch/MOS65XX/MOS65XXDisassembler.c",
      "function": "MOS65XX_getInstruction"
    },
    {
      "file": "/workspace/repo/arch/X86/X86Disassembler.c",
      "function": "translateImmediate"
    },
    {
      "file": "/workspace/repo/arch/XCore/XCoreDisassembler.c",
      "function": "Decode3OpInstruction"
    },
    {
      "file": "/workspace/repo/arch/XCore/XCoreInstPrinter.c",
      "function": "XCore_insn_extract"
    },
    {
      "file": "/workspace/repo/arch/X86/X86IntelInstPrinter.c",
      "function": "printMemOffset"
    },
    {
      "file": "/workspace/repo/arch/RISCV/RISCVDisassembler.c",
      "function": "decodeCLUIImmOperand"
    },
    {
      "file": "/workspace/repo/arch/PowerPC/PPCMapping.c",
      "function": "add_cs_detail_general"
    },
    {
      "file": "/workspace/repo/arch/WASM/WASMDisassembler.c",
      "function": "get_varuint32"
    },
    {
      "file": "/workspace/repo/cs.c",
      "function": "cs_option"
    },
    {
      "file": "/workspace/repo/arch/EVM/EVMDisassembler.c",
      "function": "EVM_getInstruction"
    }
  ]
}
RCA
