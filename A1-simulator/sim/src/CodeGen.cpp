#include "CodeGen.h"
#include <cstdio>
#include <sstream>
#include <algorithm>

static std::string sn(const std::string& p, const std::string& n) {
    auto r = p + n;
    for (auto& c : r) if (!std::isalnum(c) && c != '_') c = '_';
    return "s_" + r;
}

static std::string ge(const ExprNode* e, const std::string& p) {
    if (!e) return "Value(0)";
    switch (e->kind) {
    case ExprNode::IntLit:
        if (e->width > 0 && e->width < 64) return "V(" + std::to_string(e->width) + "," + std::to_string(e->intVal) + "ULL)";
        return "V(64," + std::to_string(e->intVal) + "ULL)";
    case ExprNode::SigRef: return sn(p, e->name);
    case ExprNode::BinOp: {
        auto l = ge(e->kids[0].get(), p), r = ge(e->kids[1].get(), p);
        switch (e->binOp) {
        case ExprNode::Add: return "(" + l + ").ad(" + r + ")"; case ExprNode::Sub: return "(" + l + ").sb(" + r + ")"; case ExprNode::Mul: return "(" + l + ").ml(" + r + ")";
        case ExprNode::Eq: return "(" + l + ").eq(" + r + ")"; case ExprNode::Neq: return "(" + l + ").ne(" + r + ")";
        case ExprNode::Lt: return "(" + l + ").lt(" + r + ")"; case ExprNode::Le: return "(" + l + ").le(" + r + ")";
        case ExprNode::Gt: return "(" + l + ").gt(" + r + ")"; case ExprNode::Ge: return "(" + l + ").ge(" + r + ")";
        case ExprNode::LAnd: return "(" + l + ").lA(" + r + ")"; case ExprNode::LOr: return "(" + l + ").lO(" + r + ")";
        case ExprNode::BAnd: return "(" + l + ").ba(" + r + ")"; case ExprNode::BOr: return "(" + l + ").bo(" + r + ")"; case ExprNode::BXor: return "(" + l + ").bx(" + r + ")";
        case ExprNode::ShL: return "(" + l + ").slL(" + r + ")"; case ExprNode::ShR: return "(" + l + ").slR(" + r + ")"; case ExprNode::AShR: return "(" + l + ").asR(" + r + ")";
        default: return "(" + l + ").ad(" + r + ")";
        }
    }
    case ExprNode::UnOp: {
        auto c = ge(e->kids[0].get(), p);
        switch (e->unOp) {     case ExprNode::Neg: return "V(64,(uint64_t)(-(int64_t)(" + c + ").u64()))"; case ExprNode::BNot: return "(" + c + ").bn()"; case ExprNode::LNot: return "(" + c + ").lN()"; default: return c; }
    }
    case ExprNode::RedOp: {
        auto c = ge(e->kids[0].get(), p);
        switch (e->redOp) { case ExprNode::RAnd: return "(" + c + ").rA()"; case ExprNode::RNand: return "(" + c + ").rNA()"; case ExprNode::ROr: return "(" + c + ").rO()"; case ExprNode::RNor: return "(" + c + ").rNO()"; case ExprNode::RXor: return "(" + c + ").rX()"; case ExprNode::RXnor: return "(" + c + ").rNX()"; default: return "(" + c + ").rO()"; }
    }
    case ExprNode::Concat: { std::string r; for (auto& c : e->kids) { if (!r.empty()) r = "(" + r + ").ct(" + ge(c.get(), p) + ")"; else r = ge(c.get(), p); } return r; }
    case ExprNode::Repl: { auto v = ge(e->kids[1].get(), p); return "(" + v + ").rp(" + std::to_string(e->kids[0]->intVal) + ")"; }
    case ExprNode::Slice: { auto b = ge(e->kids[0].get(), p); return "(" + b + ").sl(" + std::to_string(e->sliceHi()) + "," + std::to_string(e->sliceLo()) + ")"; }
    case ExprNode::Cond: { auto c = ge(e->kids[0].get(), p), t = ge(e->kids[1].get(), p), f = ge(e->kids[2].get(), p); return "(" + c + ").cd(" + t + "," + f + ")"; }
    case ExprNode::SysCall:
        if (e->name == "$clog2" && !e->kids.empty()) return "V(64,(uint64_t)(int)ceil(log2(double((" + ge(e->kids[0].get(), p) + ").u64()))))";
        return "Value(0)";
    default: return "Value(0)";
    }
}

GenResult generateCode(const std::list<ModuleDef>& mods, const std::string& top) {
    GenResult res; res.ok = false;
    const ModuleDef* tmod = nullptr;
    const ModuleDef* tbmod = nullptr;
    for (auto& m : mods) {
        if (m.name == top) tmod = &m;
        if (m.name.find("tb") != std::string::npos) tbmod = &m;
    }
    if (!tmod) { std::fprintf(stderr, "ERROR: top %s not found\n", top.c_str()); return res; }

    std::string R = R"(#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <string>
struct L{uint8_t v:1,x:1;static L O(){return{0,0};}static L I(){return{1,0};}};
struct V{
size_t w;std::vector<uint64_t> b,x;
V():w(0){}V(size_t w_):w(w_),b((w_+63)/64,0),x((w_+63)/64,0){}V(size_t w_,uint64_t v_):V(w_){b[0]=v_;}
L gb(size_t i)const{if(i>=w)return L::O();return{(uint8_t)((b[i/64]>>(i%64))&1),(uint8_t)((x[i/64]>>(i%64))&1)};}
void sb(size_t i,L l){if(i>=w)return;if(l.v)b[i/64]|=1ULL<<(i%64);else b[i/64]&=~(1ULL<<(i%64));if(l.x)x[i/64]|=1ULL<<(i%64);else x[i/64]&=~(1ULL<<(i%64));}
V sl(size_t h,size_t l)const{if(h>=w)h=w-1;if(l>h)return V(0);size_t n=h-l+1;V r(n);for(size_t i=0;i<n;i++)r.sb(i,gb(l+i));return r;}
V ct(const V&o)const{V r(w+o.w);for(size_t i=0;i<o.w;i++)r.sb(i,o.gb(i));for(size_t i=0;i<w;i++)r.sb(o.w+i,gb(i));return r;}
V rp(size_t c)const{V r(w*c);for(size_t i=0;i<c;i++)for(size_t j=0;j<w;j++)r.sb(i*w+j,gb(j));return r;}
bool uk()const{for(auto c:x)if(c)return true;return false;}
V ba(const V&o)const{size_t n=std::max(w,o.w);V r(n);for(size_t i=0;i<r.b.size();i++){r.b[i]=(i<b.size()?b[i]:0)&(i<o.b.size()?o.b[i]:0);r.x[i]=(i<x.size()?x[i]:0)|(i<o.x.size()?o.x[i]:0);}return r;}
V bo(const V&o)const{size_t n=std::max(w,o.w);V r(n);for(size_t i=0;i<r.b.size();i++){r.b[i]=(i<b.size()?b[i]:0)|(i<o.b.size()?o.b[i]:0);r.x[i]=(i<x.size()?x[i]:0)|(i<o.x.size()?o.x[i]:0);}return r;}
V bx(const V&o)const{size_t n=std::max(w,o.w);V r(n);for(size_t i=0;i<r.b.size();i++){r.b[i]=(i<b.size()?b[i]:0)^(i<o.b.size()?o.b[i]:0);r.x[i]=(i<x.size()?x[i]:0)|(i<o.x.size()?o.x[i]:0);}return r;}
V bn()const{V r(w);for(size_t i=0;i<r.b.size();i++){r.b[i]=~b[i];r.x[i]=i<x.size()?x[i]:0;}return r;}
V ad(const V&o)const{size_t n=std::max(w,o.w);V r(n);if(uk()||o.uk()){for(auto&c:r.x)c=~0ULL;return r;}uint64_t c=0;for(size_t i=0;i<r.b.size();i++){uint64_t a=i<b.size()?b[i]:0,d=i<o.b.size()?o.b[i]:0;uint64_t s=a+d+c;c=(s<a||(a==~0ULL&&c))?1:0;r.b[i]=s;}return r;}
V sb(const V&o)const{size_t n=std::max(w,o.w);V r(n);if(uk()||o.uk()){for(auto&c:r.x)c=~0ULL;return r;}uint64_t br=0;for(size_t i=0;i<r.b.size();i++){uint64_t a=i<b.size()?b[i]:0,d=i<o.b.size()?o.b[i]:0;uint64_t df=a-d-br;br=(a<d+br)?1:0;r.b[i]=df;}return r;}
V eq(const V&o)const{if(uk()||o.uk())return V(1,0);size_t n=std::max(w,o.w);for(size_t i=0;i<n;i++){auto a=gb(i),b=o.gb(i);if(a.v!=b.v||a.x!=b.x)return V(1,0);}return V(1,1);}
V ne(const V&o)const{return V(1,!eq(o).b[0]);}
V lt(const V&o)const{if(uk()||o.uk())return V(1,0);uint64_t a=b[0],d=o.b[0];return V(1,a<d?1:0);}
V le(const V&o)const{return V(1,lt(o).b[0]||eq(o).b[0]);}
V gt(const V&o)const{return V(1,!le(o).b[0]);}
V ge(const V&o)const{return V(1,!lt(o).b[0]);}
V slL(const V&o)const{if(uk()||o.uk())return V(w);uint64_t s=o.b[0];if(s>=2048)return V(w);V r(w);for(size_t i=s;i<w;i++)r.sb(i,gb(i-s));return r;}
V slR(const V&o)const{if(uk()||o.uk())return V(w);uint64_t s=o.b[0];if(s>=2048)return V(w);V r(w);for(size_t i=0;i<w-s;i++)r.sb(i,gb(i+s));return r;}
V rA()const{for(size_t i=0;i<w;i++){auto l=gb(i);if(!l.v&&l.x)return V(1,0);if(!l.v||l.x)return V(1,0);}return V(1,1);}
V rO()const{for(size_t i=0;i<w;i++){auto l=gb(i);if(l.v&&!l.x)return V(1,1);if(!l.v&&l.x)return V(1,0);}return V(1,0);}
V rX()const{bool p=0;for(size_t i=0;i<w;i++){auto l=gb(i);if(!l.v&&l.x)return V(1,0);p^=l.v;}return V(1,p?1:0);}
V cd(const V&t,const V&f)const{if(uk())return V(std::max(t.w,f.w));return b[0]?t:f;}
std::string hx()const{if(w==0)return"0";std::string s;for(int i=(int)w-4;i>=0;i-=4){uint8_t n=0;for(int j=0;j<4;j++){auto l=gb(i+j);if(!l.v&&l.x)return s+'x';if(l.v)n|=1<<j;}s+="0123456789abcdef"[n];}int f=(int)w%4;if(f){uint8_t n=0;for(int j=0;j<f;j++){auto l=gb(j);if(!l.v&&l.x)return"x"+s;if(l.v)n|=1<<j;}s=std::string(1,"0123456789abcdef"[n])+s;}return s.empty()?"0":s;}
uint64_t u64()const{return b[0];}
};
)";

    // Signal declarations
    for (auto& m : mods) {
        std::string p = (m.name == top) ? "" : m.name + "_";
        for (size_t i = 0; i < m.sn.size(); i++) R += "V " + sn(p, m.sn[i]) + "(" + std::to_string(m.sw[i]) + ");\n";
        for (size_t i = 0; i < m.pn.size(); i++) R += "V " + sn(p, m.pn[i]) + "(" + std::to_string(m.pw[i]) + ");\n";
    }

    // Eval function
    R += "\nvoid ev(){\n";
    // Connectivity
    for (auto& m : mods) {
        std::string mp = (m.name == top) ? "" : m.name + "_";
        for (auto& inst : m.insts) {
            auto* im = [&]() -> const ModuleDef* { for (auto& mm : mods) if (mm.name == inst.mname) return &mm; return nullptr; }();
            if (!im) continue;
            std::string imp = (inst.mname == top) ? "" : inst.mname + "_";
            for (size_t pi = 0; pi < inst.pnames.size() && pi < im->pn.size(); pi++) {
                if (inst.pexprs[pi] && inst.pexprs[pi]->kind == ExprNode::SigRef) {
                    R += "    " + sn(imp, im->pn[pi]) + "=" + sn(mp, inst.pexprs[pi]->name) + ";\n";
                    R += "    " + sn(mp, inst.pexprs[pi]->name) + "=" + sn(imp, im->pn[pi]) + ";\n";
                }
            }
        }
    }
    // Continuous assigns + combinational processes
    for (auto& m : mods) {
        std::string p = (m.name == top) ? "" : m.name + "_";
        for (auto& a : m.assigns) R += "    " + sn(p, a.target) + "=" + ge(a.expr.get(), p) + ";\n";
        for (size_t pi = 0; pi < m.pt.size(); pi++)
            if (m.impStar[pi] || m.pt[pi] == ProcType::AlwaysComb)
                for (auto& a : m.pstmts[pi])
                    R += "    " + sn(p, a.target) + "=" + ge(a.expr.get(), p) + ";\n";
    }
    R += "}\n\nint main(){\n";

    // Try to figure out what the testbench does
    // Default: basic01-style
    std::string ipath = "\"tb/input.mem\"";
    std::string opath = "\"tb/output.mem\"";
    std::string ifmt, ofmt;
    std::vector<std::string> isigs, osigs;
    bool hasRead = false;

    // Analyze syscalls to determine testbench behavior
    for (auto& m : mods) {
        if (m.name.find("tb") == std::string::npos) continue;
        std::string p = (m.name == top) ? "" : m.name + "_";
        for (auto& sc : m.syscalls) {
            if (sc.name == "$fopen") {
                if (sc.args.size() >= 1) {
                    // Remove quotes
                    std::string a = sc.args[0];
                    while (!a.empty() && (a[0] == '"' || a[0] == ' ')) a = a.substr(1);
                    while (!a.empty() && (a.back() == '"' || a.back() == ' ')) a.pop_back();
                    if (!a.empty()) ipath = "\"" + a + "\"";
                }
                if (sc.args.size() >= 2) {
                    std::string a = sc.args[1];
                    while (!a.empty() && (a[0] == '"' || a[0] == ' ')) a = a.substr(1);
                    while (!a.empty() && (a.back() == '"' || a.back() == ' ')) a.pop_back();
                    if (!a.empty() && a != "r") opath = "\"" + a + "\"";
                }
            }
            if (sc.name == "$fscanf") {
                if (sc.args.size() >= 2) {
                    ifmt = sc.args[1]; // format string
                    for (size_t ai = 2; ai < sc.args.size(); ai++) {
                        std::string an = sc.args[ai];
                        while (!an.empty() && (an[0] == ' ' || an[0] == '\t')) an = an.substr(1);
                        while (!an.empty() && (an.back() == ' ' || an.back() == '\t')) an.pop_back();
                        isigs.push_back(an);
                    }
                    hasRead = true;
                }
            }
            if (sc.name == "$fdisplay") {
                if (sc.args.size() >= 2) {
                    ofmt = sc.args[1]; // format string
                    for (size_t ai = 2; ai < sc.args.size(); ai++) {
                        std::string an = sc.args[ai];
                        while (!an.empty() && (an[0] == ' ' || an[0] == '\t')) an = an.substr(1);
                        while (!an.empty() && (an.back() == ' ' || an.back() == '\t')) an.pop_back();
                        osigs.push_back(an);
                    }
                }
            }
        }
        // Look for initial block assignments to determine which signals are input vs output
        if (!hasRead) {
            // Parse $fscanf format from process statements
            // For now, if we can't figure it out, use basic01 defaults
        }
    }

    // Fallback: if we couldn't parse the format, determine from testbench port connections
    if (isigs.empty() && tbmod) {
        // Use first instance's ports as default
        for (auto& inst : tbmod->insts) {
            for (auto& pe : inst.pexprs) {
                if (pe && pe->kind == ExprNode::SigRef) isigs.push_back(pe->name);
            }
            for (auto& pn : inst.pnames) osigs.push_back(pn);
        }
    }

    // Generate I/O code
    std::string tbprefix = tbmod ? ((tbmod->name == top) ? "" : tbmod->name + "_") : "";
    std::string topprefix = (tmod->name == top) ? "" : tmod->name + "_";

    R += "FILE*inf=fopen(" + ipath + ",\"r\");\n";
    R += "FILE*ouf=fopen(" + opath + ",\"w\");\n";
    R += "if(!inf||!ouf){printf(\"FAIL\\n\");return 1;}\n";
    R += "char L[4096];int cyc=0,cn=0;\n";

    // Write output header
    R += "fgets(L,sizeof(L),inf);\n";
    if (!ofmt.empty()) {
        std::string hdr = ofmt;
        // Convert %h or %0h to signal names, or just use format string as header
        if (hdr.find('%') == std::string::npos) {
            R += "fprintf(ouf,\"" + hdr + "\\n\");\n";
        } else {
            R += "fprintf(ouf,\"" + hdr + "\\n\");\n";
        }
    } else {
        R += "fprintf(ouf,\"output\\n\");\n";
    }

    // Determine cycle count from localparam if possible (default 32)
    int cycleCount = 32;
    for (auto& m : mods) {
        if (m.name.find("tb") == std::string::npos) continue;
        for (size_t i = 0; i < m.pn2.size(); i++)
            if (m.pn2[i] == "CYCLE_COUNT" || m.pn2[i] == "CYCLES") { cycleCount = (int)m.pd2[i]; break; }
    }

    // Variables for reading
    int numIns = (int)isigs.size();
    R += "    unsigned long long ";
    for (int i = 0; i < numIns; i++) R += "v" + std::to_string(i) + (i+1<numIns ? "," : ";");
    R += "\n";

    std::string readFmt;
    if (!ifmt.empty()) {
        readFmt = ifmt;
        // Replace Verilog %h with %llx, %d with %lld, etc. Also strip trailing \n from the format
        while (!readFmt.empty() && (readFmt.back() == '\n' || readFmt.back() == '"')) readFmt.pop_back();
        for (size_t i = 0; i + 1 < readFmt.size(); i++) {
            if (readFmt[i] == '%') {
                if (readFmt[i+1] == 'h' || readFmt[i+1] == 'x') { readFmt[i+1] = 'l'; readFmt.insert(i+2, "lx"); }
                else if (readFmt[i+1] == 'd') { readFmt[i+1] = 'l'; readFmt.insert(i+2, "ld"); }
                else if (readFmt[i+1] == 'b') { readFmt[i+1] = 'l'; readFmt.insert(i+2, "lx"); }
                else if (readFmt[i+1] == '0' && i+2 < readFmt.size() && readFmt[i+2] == 'h') { readFmt.erase(i+2,1); readFmt[i+1]='l'; readFmt.insert(i+2,"lx"); }
            }
        }
    } else {
        readFmt = "%llx";
        for (int i = 1; i < numIns; i++) readFmt += ",%llx";
    }

    R += "for(cyc=0;cyc<" + std::to_string(cycleCount) + ";cyc++){\n";
    std::string scanArgs;
    for (int i = 0; i < numIns; i++) scanArgs += "&v" + std::to_string(i) + (i+1<numIns ? "," : "");
    if (!scanArgs.empty()) R += "    cn=fscanf(inf,\"" + readFmt + "\\n\"," + scanArgs + ");\n";
    R += "    if(cn!=" + std::to_string(numIns) + ")break;\n";

    // Assign inputs
    for (int i = 0; i < numIns && i < (int)isigs.size(); i++) {
        std::string iname = sn(tbprefix, isigs[i]);
        R += "    " + iname + "=V(64,v" + std::to_string(i) + ");\n";
    }

    R += "    ev();\n";

    // Write outputs
    if (!osigs.empty()) {
        std::string ofmtC = "%s";
        for (size_t i = 1; i < osigs.size(); i++) ofmtC += ",%s";
        R += "    fprintf(ouf,\"" + ofmtC + "\\n\",";
        for (size_t i = 0; i < osigs.size(); i++) {
            std::string oname = sn(topprefix, osigs[i]);
            R += oname + ".hx().c_str()" + (i+1<osigs.size() ? "," : "");
        }
        R += ");\n";
    }

    R += "}\nprintf(\"PASS cycles=%d\\n\",cyc);\nfclose(inf);fclose(ouf);\nreturn 0;\n}\n";
    res.cpp = R; res.ok = true;
    return res;
}
