#pragma once

#include "Lexer.h"
#include <string>
#include <vector>
#include <list>
#include <cstdint>
#include <memory>

struct ExprNode;
using ExprPtr = std::unique_ptr<ExprNode>;

enum class SigType : uint8_t { Wire, Reg, Integer };
enum class PortDir : uint8_t { Input, Output, Inout };
enum class ProcType : uint8_t { Always, AlwaysComb, AlwaysFF, Initial };
enum class EdgeType : uint8_t { None, PosEdge, NegEdge };

struct ExprNode {
    enum Kind { SigRef, IntLit, StrLit, BinOp, UnOp, RedOp, Concat, Repl, Slice, Cond, SysCall } kind;
    enum BinOpT { Add, Sub, Mul, Div, Mod, Eq, Neq, Lt, Le, Gt, Ge, LAnd, LOr, BAnd, BOr, BXor, ShL, ShR, AShR };
    enum UnOpT { Neg, BNot, LNot };
    enum RedOpT { RAnd, RNand, ROr, RNor, RXor, RXnor };
    BinOpT binOp; UnOpT unOp; RedOpT redOp;
    std::string name; uint64_t intVal; size_t width; bool isSigned;
    std::vector<ExprPtr> kids;

    static ExprPtr ref(const std::string& n, size_t w = 1) { ExprPtr e(new ExprNode); e->kind = SigRef; e->name = n; e->width = w; return e; }
    static ExprPtr lit(uint64_t v, size_t w = 64) { ExprPtr e(new ExprNode); e->kind = IntLit; e->intVal = v; e->width = w; return e; }
    static ExprPtr bin(BinOpT op, ExprPtr l, ExprPtr r, size_t w = 1) {
        ExprPtr e(new ExprNode); e->kind = BinOp; e->binOp = op; e->width = w;
        e->kids.push_back(std::move(l)); e->kids.push_back(std::move(r)); return e;
    }
    static ExprPtr un(UnOpT op, ExprPtr c, size_t w = 1) {
        ExprPtr e(new ExprNode); e->kind = UnOp; e->unOp = op; e->width = w; e->kids.push_back(std::move(c)); return e;
    }
    static ExprPtr red(RedOpT op, ExprPtr c) {
        ExprPtr e(new ExprNode); e->kind = RedOp; e->redOp = op; e->width = 1; e->kids.push_back(std::move(c)); return e;
    }
    static ExprPtr cat(std::vector<ExprPtr> args, size_t w) {
        ExprPtr e(new ExprNode); e->kind = Concat; e->width = w; e->kids = std::move(args); return e;
    }
    static ExprPtr rep(ExprPtr cnt, ExprPtr val, size_t w) {
        ExprPtr e(new ExprNode); e->kind = Repl; e->width = w;
        e->kids.push_back(std::move(cnt)); e->kids.push_back(std::move(val)); return e;
    }
    static ExprPtr slc(ExprPtr base, size_t h, size_t l, size_t w) {
        ExprPtr e(new ExprNode); e->kind = Slice; e->intVal = h; e->name = std::to_string(l); e->width = w; e->kids.push_back(std::move(base)); return e;
    }
    static ExprPtr cond(ExprPtr c, ExprPtr t, ExprPtr f, size_t w) {
        ExprPtr e(new ExprNode); e->kind = Cond; e->width = w;
        e->kids.push_back(std::move(c)); e->kids.push_back(std::move(t)); e->kids.push_back(std::move(f)); return e;
    }
    static ExprPtr sys(const std::string& n, std::vector<ExprPtr> args, size_t w = 64) {
        ExprPtr e(new ExprNode); e->kind = SysCall; e->name = n; e->kids = std::move(args); e->width = w; return e;
    }
    size_t sliceHi() const { return (size_t)intVal; }
    size_t sliceLo() const { return (size_t)std::stoul(name); }
};

struct AssignStmt { std::string target; size_t tw; bool nba, ps; size_t phi, plo; ExprPtr expr;
    AssignStmt() : tw(1), nba(false), ps(false), phi(0), plo(0) {}
};
struct SysCall { std::string name; std::vector<std::string> args; };
struct InstanceInfo { std::string iname, mname; std::vector<std::string> pnames; std::vector<ExprPtr> pexprs; };

struct ModuleDef {
    std::string name;
    std::vector<std::string> pn;     // port names
    std::vector<size_t> pw;          // port widths
    std::vector<PortDir> pd;         // port directions
    std::vector<std::string> sn;     // signal names
    std::vector<size_t> sw;          // signal widths
    std::vector<SigType> st;         // signal types
    std::vector<bool> sm;            // signal is memory
    std::vector<size_t> smd;         // signal mem depth
    std::vector<AssignStmt> assigns; // continuous assignments
    std::vector<ProcType> pt;        // process types
    std::vector<EdgeType> et;        // edge types
    std::vector<std::string> es;     // edge signal names
    std::vector<bool> impStar;       // @(*) flag
    std::vector<std::vector<AssignStmt>> pstmts; // process statements
    std::vector<std::string> pn2; // param names
    std::vector<uint64_t> pd2;   // param defaults
    std::vector<InstanceInfo> insts; // instances
    std::vector<SysCall> syscalls; // system calls from initial blocks

    size_t sigIdx(const std::string& n) const { for (size_t i = 0; i < sn.size(); i++) if (sn[i] == n) return i; return SIZE_MAX; }
    size_t portIdx(const std::string& n) const { for (size_t i = 0; i < pn.size(); i++) if (pn[i] == n) return i; return SIZE_MAX; }
};

class Parser final {
public:
    explicit Parser(const std::string& src) : lexer(src) {}
    bool parse();
    std::list<ModuleDef>&& takeMods() { return std::move(modules); }
    const std::list<ModuleDef>& mods() const { return modules; }
private:
    Lexer lexer;
    std::list<ModuleDef> modules;
    Token peek(size_t a = 0) { return lexer.peek(a); }
    Token consume() { return lexer.consume(); }
    bool expect(TokenKind k) { return lexer.expect(k); }

    ModuleDef parseModule();
    void parsePortL(ModuleDef& m);
    void parseAPort(ModuleDef& m);
    void parseParamL(ModuleDef& m);
    void parseMember(ModuleDef& m);
    void parseSig(ModuleDef& m);
    void parseNet(ModuleDef& m);
    void parseCA(ModuleDef& m);
    void parseAB(ModuleDef& m, ProcType t);
    void parseIB(ModuleDef& m);
    void parsePS(ModuleDef& m, std::vector<AssignStmt>& ss, TokenKind ek);
    void parseStmt(ModuleDef& m, std::vector<AssignStmt>& ss, TokenKind ek);
    void parseInst(ModuleDef& m);
    ExprPtr parseE();
    ExprPtr parseEB(int mp);
    ExprPtr parseEP();
    ExprPtr parseN();
    uint64_t ec(const ExprPtr& e) { return e && e->kind == ExprNode::IntLit ? e->intVal : 0; }
};
