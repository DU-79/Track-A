#include "Compiler.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <sys/stat.h>

struct Compiler::Impl {
    std::unordered_map<std::string, std::string> defs;
    std::vector<std::string> idirs;
};

static bool exists(const std::string& p) { struct stat s; return stat(p.c_str(), &s) == 0; }
static std::string pdir(const std::string& p) { auto pos = p.find_last_of("/\\"); return (pos != std::string::npos) ? p.substr(0, pos) : "."; }

Compiler::Compiler() : impl(new Impl) {}
Compiler::~Compiler() = default;

bool Compiler::parseFilelist(const std::string& path) {
    std::ifstream fl(path);
    if (!fl.is_open()) { std::fprintf(stderr, "ERROR: cannot open %s\n", path.c_str()); return false; }
    impl->idirs.push_back(pdir(path));
    std::string line;
    while (std::getline(fl, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) line.pop_back();
        if (line.empty() || line[0] == '#' || line[0] == '/') continue;
        if (line[0] == '+') { if (line.size() > 2 && line[1] == 'I') impl->idirs.push_back(line.substr(2)); continue; }
        if (line[0] == '-') continue;
        std::string fp = (line[0] == '/' || line[0] == '\\' || (line.size() > 1 && line[1] == ':')) ? line : pdir(path) + "/" + line;
        for (auto& c : fp) if (c == '\\') c = '/';
        files.push_back(fp);
        std::ifstream f(fp);
        if (!f.is_open()) { std::fprintf(stderr, "WARN: cannot open %s\n", fp.c_str()); continue; }
        std::stringstream ss; ss << f.rdbuf();
        std::string src = ss.str();
        std::string pp = preproc(src, pdir(fp));
        Parser parser(pp);
        if (parser.parse()) {
            mods.splice(mods.end(), parser.takeMods());
        }
    }
    return !mods.empty();
}

std::string Compiler::preproc(const std::string& src, const std::string& dir) {
    std::string r; size_t i = 0, n = src.size();
    while (i < n) {
        if ((i == 0 || src[i-1] == '\n')) {
            size_t j = i; while (j < n && (src[j] == ' ' || src[j] == '\t')) j++;
            if (j < n && src[j] == '`') {
                i = j + 1; std::string dn;
                while (i < n && (std::isalpha(src[i]) || src[i] == '_')) dn += src[i++];
                if (dn == "include") {
                    while (i < n && (src[i] == ' ' || src[i] == '\t')) i++;
                    std::string ip;
                    if (i < n && src[i] == '"') { i++; while (i < n && src[i] != '"') ip += src[i++]; if (i < n) i++; }
                    std::string rp;
                    for (auto& d : impl->idirs) { std::string t = d + "/" + ip; for (auto& c : t) if (c == '\\') c = '/'; if (exists(t)) { rp = t; break; } }
                    if (rp.empty()) { rp = dir + "/" + ip; for (auto& c : rp) if (c == '\\') c = '/'; if (!exists(rp)) rp.clear(); }
                    if (!rp.empty()) { std::ifstream f(rp); if (f.is_open()) { std::stringstream ss; ss << f.rdbuf(); r += preproc(ss.str(), pdir(rp)); } }
                    while (i < n && src[i] != '\n') i++;
                } else if (dn == "define") {
                    while (i < n && (src[i] == ' ' || src[i] == '\t')) i++;
                    std::string mn; while (i < n && (std::isalnum(src[i]) || src[i] == '_')) mn += src[i++];
                    while (i < n && (src[i] == ' ' || src[i] == '\t')) i++;
                    std::string mv; while (i < n && src[i] != '\n') mv += src[i++];
                    impl->defs[mn] = mv;
                } else if (dn == "ifdef" || dn == "ifndef") {
                    bool neg = (dn == "ifndef");
                    while (i < n && (src[i] == ' ' || src[i] == '\t')) i++;
                    std::string mn; while (i < n && (std::isalnum(src[i]) || src[i] == '_')) mn += src[i++];
                    bool defined = impl->defs.find(mn) != impl->defs.end();
                    if (neg) defined = !defined;
                    if (!defined) {
                        int dep = 1;
                        while (i < n && dep > 0) {
                            auto nl = src.find('\n', i); if (nl == std::string::npos) nl = n;
                            auto l = src.substr(i, nl - i);
                            if (l.find("`ifdef") != std::string::npos || l.find("`ifndef") != std::string::npos) dep++;
                            else if (l.find("`endif") != std::string::npos) dep--;
                            else if (dep == 1 && l.find("`else") != std::string::npos) break;
                            i = nl + 1;
                        }
                    }
                    while (i < n && src[i] != '\n') i++;
                } else if (dn == "else") {
                    while (i < n) { auto nl = src.find('\n', i); if (nl == std::string::npos) nl = n; if (src.substr(i, nl - i).find("`endif") != std::string::npos) { i = nl; break; } i = nl + 1; }
                } else if (dn == "endif") { while (i < n && src[i] != '\n') i++; }
                else { while (i < n && src[i] != '\n') i++; }
                continue;
            }
        }
        if (src[i] == '`') {
            size_t j = i + 1; std::string mn;
            while (j < n && (std::isalnum(src[j]) || src[j] == '_')) mn += src[j++];
            if (!mn.empty()) { auto it = impl->defs.find(mn); if (it != impl->defs.end()) { r += it->second; i = j; continue; } }
        }
        r += src[i++];
    }
    return r;
}

void Compiler::dumpStats() const {
    size_t tp = 0, ts = 0;
    for (auto& m : mods) { tp += m.pn.size(); ts += m.sn.size(); }
    std::printf("Parsed %zu modules (%zu ports, %zu signals)\n", mods.size(), tp, ts);
}

const ModuleDef* Compiler::find(const std::string& name) const {
    for (auto& m : mods) if (m.name == name) return &m;
    return nullptr;
}
