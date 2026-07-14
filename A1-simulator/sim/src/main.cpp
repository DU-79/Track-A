#include "Compiler.h"
#include "CodeGen.h"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fstream>

int main(int argc, char* argv[]) {
    if (argc < 2 || std::strcmp(argv[1], "--compile")) {
        std::fprintf(stderr, "Usage: %s --compile -f <filelist> --top <module> -o <output>\n", argv[0]);
        return 1;
    }

    std::string filelist, topModule = "tb", output = "sim.out";
    for (int i = 2; i < argc; i++) {
        if (!std::strcmp(argv[i], "-f") && i + 1 < argc) filelist = argv[++i];
        else if (!std::strcmp(argv[i], "--top") && i + 1 < argc) topModule = argv[++i];
        else if (!std::strcmp(argv[i], "-o") && i + 1 < argc) output = argv[++i];
    }
    if (filelist.empty()) { std::fprintf(stderr, "ERROR: -f required\n"); return 1; }

    std::printf("Parsing: %s\n", filelist.c_str());
    Compiler compiler;
    if (!compiler.parseFilelist(filelist)) { std::fprintf(stderr, "ERROR: parse failed\n"); return 1; }
    compiler.dumpStats();

    std::printf("Generating code for top: %s\n", topModule.c_str());
    auto res = generateCode(compiler.modules(), topModule);
    if (!res.ok) { std::fprintf(stderr, "ERROR: codegen failed\n"); return 1; }

    std::string src = output + ".cpp";
    { std::ofstream f(src.c_str()); if (!f.is_open()) { std::fprintf(stderr, "ERROR: cannot write\n"); return 1; } f << res.cpp; }

    std::string cmd = "g++ -std=c++11 -O2 -o " + output + " " + src + " -lm";
    std::printf("Compiling: %s\n", cmd.c_str());
    int ret = std::system(cmd.c_str());
    if (ret != 0) { std::fprintf(stderr, "ERROR: compilation failed\n"); return 1; }

    std::printf("Generated: %s\n", output.c_str());
    return 0;
}
