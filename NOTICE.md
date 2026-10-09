# Credits and provenance

The native Steam bridge and the loader detour come from
[NotProton](https://github.com/NotProtonNot/NotProton), revision
`599ebf6a4cfa52b46c03299170ccbde8f8fe2205`.

The five files in `vendor/notproton-ntdll/` are unmodified copies of
`ntdll-patch/{resolve.py,apply.py,detour.c,shim.S,link.ld}` at that revision.
Their original notices are preserved. See LICENSE (GNU GPL version 3).

Our build script generates a modified copy of `detour.c` in a local build
directory: Windows calling conventions (`ms_abi`) are made explicit for
compilation with Apple's clang targeting x86_64 ELF. The assembly shim and
linker layout remain upstream code. This repository is distributed under GPL-3.0.

CrossOver, Rosetta, Steam and AION 2 are supplied separately by their respective
owners. No CrossOver DLL, Steam credential, game file or FEX source modification
is distributed here. This project is not affiliated with those vendors.
