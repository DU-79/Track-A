#include "ModuleDef.h"
#include <cstdio>

bool Parser::parse() {
    while (peek().kind != TokenKind::Eof) {
        if (peek().kind == TokenKind::Module)
            modules.push_back(parseModule());
        else consume();
    }
    return !modules.empty();
}

ModuleDef Parser::parseModule() {
    ModuleDef m;
    expect(TokenKind::Module);
    m.name = consume().text;
    if (peek().kind == TokenKind::Hash) { consume(); parseParamL(m); }
    if (peek().kind == TokenKind::OpenParen) parsePortL(m);
    expect(TokenKind::Semicolon);
    while (peek().kind != TokenKind::Endmodule && peek().kind != TokenKind::Eof) parseMember(m);
    if (peek().kind == TokenKind::Endmodule) consume();
    return m;
}

void Parser::parsePortL(ModuleDef& m) {
    consume();
    while (peek().kind != TokenKind::CloseParen && peek().kind != TokenKind::Eof) {
        parseAPort(m);
        if (peek().kind == TokenKind::Comma) consume();
    }
    if (peek().kind == TokenKind::CloseParen) consume();
}

void Parser::parseAPort(ModuleDef& m) {
    PortDir d = PortDir::Input;
    if (peek().kind == TokenKind::Input) { d = PortDir::Input; consume(); }
    else if (peek().kind == TokenKind::Output) { d = PortDir::Output; consume(); }
    else if (peek().kind == TokenKind::Inout) { d = PortDir::Inout; consume(); }
    if (peek().kind == TokenKind::Wire || peek().kind == TokenKind::Reg) consume();
    size_t w = 1;
    if (peek().kind == TokenKind::OpenBracket) {
        consume(); auto h = parseE(); expect(TokenKind::Colon); auto l = parseE(); expect(TokenKind::CloseBracket);
        w = (size_t)(ec(h) - ec(l) + 1);
    }
    m.pn.push_back(consume().text); m.pw.push_back(w); m.pd.push_back(d);
}

void Parser::parseParamL(ModuleDef& m) {
    if (peek().kind != TokenKind::OpenParen) return;
    consume();
    while (peek().kind != TokenKind::CloseParen && peek().kind != TokenKind::Eof) {
        if (peek().kind == TokenKind::Parameter || peek().kind == TokenKind::Localparam) consume();
        if (peek().kind == TokenKind::Integer) consume();
        std::string n = consume().text;
        uint64_t v = 0;
        if (peek().kind == TokenKind::AssignOp) { consume(); v = ec(parseE()); }
        m.pn2.push_back(n); m.pd2.push_back(v);
        if (peek().kind == TokenKind::Comma) consume();
        else if (peek().kind == TokenKind::Semicolon) consume();
    }
    if (peek().kind == TokenKind::CloseParen) consume();
}

void Parser::parseMember(ModuleDef& m) {
    switch (peek().kind) {
    case TokenKind::Input: case TokenKind::Output: case TokenKind::Inout: {
        PortDir d = (peek().kind == TokenKind::Input) ? PortDir::Input :
                    (peek().kind == TokenKind::Output) ? PortDir::Output : PortDir::Inout;
        consume(); size_t w = 1;
        if (peek().kind == TokenKind::Wire || peek().kind == TokenKind::Reg) consume();
        if (peek().kind == TokenKind::OpenBracket) {
            consume(); auto h = parseE(); expect(TokenKind::Colon); auto l = parseE(); expect(TokenKind::CloseBracket);
            w = (size_t)(ec(h) - ec(l) + 1);
        }
        m.pn.push_back(consume().text); m.pw.push_back(w); m.pd.push_back(d);
        expect(TokenKind::Semicolon); break;
    }
    case TokenKind::Wire: parseNet(m); break;
    case TokenKind::Reg: case TokenKind::Integer: parseSig(m); break;
    case TokenKind::Assign: parseCA(m); break;
    case TokenKind::Always: consume(); parseAB(m, ProcType::Always); break;
    case TokenKind::AlwaysComb: consume(); parseAB(m, ProcType::AlwaysComb); break;
    case TokenKind::Initial: consume(); parseIB(m); break;
    case TokenKind::Semicolon: consume(); break;
    default:
        if (peek().kind == TokenKind::Identifier && peek(1).kind == TokenKind::Identifier) {
            parseInst(m);
        } else consume();
        break;
    }
}

void Parser::parseSig(ModuleDef& m) {
    SigType t = (peek().kind == TokenKind::Integer) ? SigType::Integer : SigType::Reg;
    consume();
    size_t w = (t == SigType::Integer) ? 32 : 1;
    if (peek().kind == TokenKind::OpenBracket) {
        consume(); auto h = parseE(); expect(TokenKind::Colon); auto l = parseE(); expect(TokenKind::CloseBracket);
        w = (size_t)(ec(h) - ec(l) + 1);
    }
    while (peek().kind == TokenKind::Identifier) {
        std::string n = consume().text;
        bool mem = false; size_t md = 0;
        if (peek().kind == TokenKind::OpenBracket) {
            consume(); auto h = parseE(); mem = true; md = (size_t)ec(h);
            if (peek().kind == TokenKind::Colon) { consume(); auto l = parseE(); md = (size_t)(ec(h) - ec(l) + 1); }
            expect(TokenKind::CloseBracket);
        }
        m.sn.push_back(n); m.sw.push_back(w); m.st.push_back(t); m.sm.push_back(mem); m.smd.push_back(md);
        if (peek().kind == TokenKind::Comma) consume(); else break;
    }
    expect(TokenKind::Semicolon);
}

void Parser::parseNet(ModuleDef& m) {
    consume();
    size_t w = 1;
    if (peek().kind == TokenKind::OpenBracket) {
        consume(); auto h = parseE(); expect(TokenKind::Colon); auto l = parseE(); expect(TokenKind::CloseBracket);
        w = (size_t)(ec(h) - ec(l) + 1);
    }
    while (peek().kind == TokenKind::Identifier) {
        m.sn.push_back(consume().text); m.sw.push_back(w); m.st.push_back(SigType::Wire); m.sm.push_back(false); m.smd.push_back(0);
        if (peek().kind == TokenKind::Comma) consume(); else break;
    }
    expect(TokenKind::Semicolon);
}

void Parser::parseCA(ModuleDef& m) {
    consume();
    while (true) {
        AssignStmt a;
        a.target = consume().text;
        if (peek().kind == TokenKind::OpenBracket) {
            consume(); auto h = parseE();
            if (peek().kind == TokenKind::Colon) { consume(); auto l = parseE(); a.ps = true; a.phi = (size_t)ec(h); a.plo = (size_t)ec(l); a.tw = a.phi - a.plo + 1; }
            expect(TokenKind::CloseBracket);
        }
        if (peek().kind == TokenKind::AssignOp) { consume(); a.nba = false; a.expr = parseE(); }
        m.assigns.push_back(std::move(a));
        if (peek().kind == TokenKind::Comma) consume(); else break;
    }
    expect(TokenKind::Semicolon);
}

void Parser::parseAB(ModuleDef& m, ProcType t) {
    m.pt.push_back(t);
    EdgeType e = EdgeType::None; std::string es; bool is = false;
    if (peek().kind == TokenKind::At) {
        consume();
        if (peek().kind == TokenKind::OpenParen) {
            consume();
            if (peek().kind == TokenKind::Star) { consume(); is = true; }
            else if (peek().kind == TokenKind::PosEdge || peek().kind == TokenKind::NegEdge) {
                e = (peek().kind == TokenKind::PosEdge) ? EdgeType::PosEdge : EdgeType::NegEdge; consume();
                es = consume().text;
            } else if (peek().kind == TokenKind::Identifier) {
                es = consume().text; is = true;
            }
            if (peek().kind == TokenKind::CloseParen) consume();
        }
    }
    m.et.push_back(e); m.es.push_back(es); m.impStar.push_back(is);
    std::vector<AssignStmt> ss;
    parsePS(m, ss, TokenKind::Endmodule);
    m.pstmts.push_back(std::move(ss));
}

void Parser::parseIB(ModuleDef& m) {
    m.pt.push_back(ProcType::Initial);
    m.et.push_back(EdgeType::None); m.es.push_back(""); m.impStar.push_back(false);
    std::vector<AssignStmt> ss;
    parsePS(m, ss, TokenKind::Endmodule);
    m.pstmts.push_back(std::move(ss));
}

void Parser::parsePS(ModuleDef& m, std::vector<AssignStmt>& ss, TokenKind ek) {
    if (peek().kind == TokenKind::Begin) {
        consume();
        while (peek().kind != TokenKind::End && peek().kind != TokenKind::Eof)
            parseStmt(m, ss, TokenKind::End);
        if (peek().kind == TokenKind::End) consume();
    } else parseStmt(m, ss, ek);
}

void Parser::parseStmt(ModuleDef& m, std::vector<AssignStmt>& ss, TokenKind ek) {
    (void)m; (void)ek;
    switch (peek().kind) {
    case TokenKind::Begin:
        consume();
        while (peek().kind != TokenKind::End && peek().kind != TokenKind::Eof)
            parseStmt(m, ss, TokenKind::End);
        if (peek().kind == TokenKind::End) consume();
        break;
    case TokenKind::End: case TokenKind::Endcase: return;
    case TokenKind::Semicolon: consume(); break;
    case TokenKind::If: {
        consume();
        if (peek().kind == TokenKind::OpenParen) { consume(); parseE(); expect(TokenKind::CloseParen); }
        parsePS(m, ss, ek);
        if (peek().kind == TokenKind::Else) { consume(); parsePS(m, ss, ek); }
        break;
    }
    case TokenKind::For: {
        consume();
        if (peek().kind == TokenKind::OpenParen) {
            consume();
            if (peek().kind == TokenKind::Semicolon) consume(); else { parseE(); expect(TokenKind::Semicolon); }
            if (peek().kind == TokenKind::Semicolon) consume(); else { parseE(); expect(TokenKind::Semicolon); }
            if (peek().kind == TokenKind::CloseParen) consume(); else { parseE(); expect(TokenKind::CloseParen); }
        }
        parsePS(m, ss, ek); break;
    }
    case TokenKind::Case: {
        consume();
        if (peek().kind == TokenKind::OpenParen) { consume(); parseE(); expect(TokenKind::CloseParen); }
        while (peek().kind != TokenKind::Endcase && peek().kind != TokenKind::Eof) {
            if (peek().kind == TokenKind::Default) { consume(); if (peek().kind == TokenKind::Colon) consume(); }
            else { parseE(); if (peek().kind == TokenKind::Colon) consume(); }
            parsePS(m, ss, TokenKind::Endcase);
        }
        if (peek().kind == TokenKind::Endcase) consume(); break;
    }
    case TokenKind::Hash: { consume(); parseE(); if (peek().kind == TokenKind::Semicolon) consume(); break; }
    case TokenKind::At: {
        consume();
        if (peek().kind == TokenKind::OpenParen) {
            consume();
            if (peek().kind == TokenKind::PosEdge || peek().kind == TokenKind::NegEdge) consume();
            if (peek().kind == TokenKind::Identifier) consume();
            if (peek().kind == TokenKind::CloseParen) consume();
        }
        parseStmt(m, ss, ek); break;
    }
    case TokenKind::SysDisplay: case TokenKind::SysFopen: case TokenKind::SysFgets:
    case TokenKind::SysFscanf: case TokenKind::SysFdisplay: case TokenKind::SysFclose:
    case TokenKind::SysReadmemh: case TokenKind::SysFinish: case TokenKind::SysTime:
    case TokenKind::SysDumpvars: case TokenKind::SysFwrite: case TokenKind::SysClog2: {
        Token sytk = consume();
        SysCall sc;
        sc.name = sytk.text;
        if (peek().kind == TokenKind::OpenParen) {
            consume();
            while (peek().kind != TokenKind::CloseParen && peek().kind != TokenKind::Eof) {
                // Save raw argument text
                size_t startDepth = 0;
                std::string arg;
                while (peek().kind != TokenKind::Comma && peek().kind != TokenKind::CloseParen && peek().kind != TokenKind::Eof) {
                    if (peek().kind == TokenKind::OpenParen) startDepth++;
                    if (peek().kind == TokenKind::CloseParen) { if (startDepth == 0) break; startDepth--; }
                    arg += consume().text;
                    if (peek().kind != TokenKind::Comma && peek().kind != TokenKind::CloseParen && peek().kind != TokenKind::Eof)
                        arg += " ";
                }
                sc.args.push_back(arg);
                if (peek().kind == TokenKind::Comma) consume();
            }
            if (peek().kind == TokenKind::CloseParen) consume();
        }
        m.syscalls.push_back(sc);
        expect(TokenKind::Semicolon); break;
    }
    default:
        if (peek().kind == TokenKind::Identifier &&
            (peek(1).kind == TokenKind::AssignOp || peek(1).kind == TokenKind::NBAOp)) {
            AssignStmt a; a.target = consume().text;
            a.nba = (peek().kind == TokenKind::NBAOp);
            consume(); a.expr = parseE();
            ss.push_back(std::move(a));
            expect(TokenKind::Semicolon);
        } else consume();
        break;
    }
}

void Parser::parseInst(ModuleDef& m) {
    InstanceInfo ii;
    ii.mname = consume().text;
    ii.iname = consume().text;
    if (peek().kind == TokenKind::OpenParen) {
        consume();
        while (peek().kind != TokenKind::CloseParen && peek().kind != TokenKind::Eof) {
            if (peek().kind == TokenKind::Dot) {
                consume(); ii.pnames.push_back(consume().text);
                if (peek().kind == TokenKind::OpenParen) {
                    consume();
                    if (peek().kind != TokenKind::CloseParen) ii.pexprs.push_back(parseE());
                    else ii.pexprs.push_back(ExprPtr(nullptr));
                    if (peek().kind == TokenKind::CloseParen) consume();
                }
            } else {
                ii.pexprs.push_back(parseE());
            }
            if (peek().kind == TokenKind::Comma) consume();
        }
        if (peek().kind == TokenKind::CloseParen) consume();
    }
    expect(TokenKind::Semicolon);
    m.insts.push_back(std::move(ii));
}

ExprPtr Parser::parseE() { return parseEB(0); }

ExprPtr Parser::parseEB(int mp) {
    auto l = parseEP();
    while (true) {
        auto tk = peek();
        struct { int p; ExprNode::BinOpT o; } bi = {0, ExprNode::Add};
        bool isB = true;
        switch (tk.kind) {
        case TokenKind::Plus: bi = {10, ExprNode::Add}; break;
        case TokenKind::Minus: bi = {10, ExprNode::Sub}; break;
        case TokenKind::Star_op: bi = {11, ExprNode::Mul}; break;
        case TokenKind::Slash: bi = {11, ExprNode::Div}; break;
        case TokenKind::Percent: bi = {11, ExprNode::Mod}; break;
        case TokenKind::Eq: bi = {4, ExprNode::Eq}; break;
        case TokenKind::Neq: bi = {4, ExprNode::Neq}; break;
        case TokenKind::Lt: bi = {5, ExprNode::Lt}; break;
        case TokenKind::Le: bi = {5, ExprNode::Le}; break;
        case TokenKind::Gt: bi = {5, ExprNode::Gt}; break;
        case TokenKind::Ge: bi = {5, ExprNode::Ge}; break;
        case TokenKind::LogAnd: bi = {2, ExprNode::LAnd}; break;
        case TokenKind::LogOr: bi = {1, ExprNode::LOr}; break;
        case TokenKind::Amp: bi = {7, ExprNode::BAnd}; break;
        case TokenKind::Pipe: bi = {6, ExprNode::BOr}; break;
        case TokenKind::Caret: bi = {6, ExprNode::BXor}; break;
        case TokenKind::ShiftLeft: bi = {9, ExprNode::ShL}; break;
        case TokenKind::ShiftRight: bi = {9, ExprNode::ShR}; break;
        default: isB = false; break;
        }
        if (!isB || bi.p < mp) break;
        consume();
        auto r = parseEB(bi.p + 1);
        l = ExprNode::bin(bi.o, std::move(l), std::move(r), std::max(l->width, r->width));
    }
    if (peek().kind == TokenKind::Question) {
        consume(); auto t = parseE(); expect(TokenKind::Colon); auto f = parseE();
        l = ExprNode::cond(std::move(l), std::move(t), std::move(f), std::max(t->width, f->width));
    }
    return l;
}

ExprPtr Parser::parseEP() {
    switch (peek().kind) {
    case TokenKind::Minus: consume(); return ExprNode::un(ExprNode::Neg, parseEP());
    case TokenKind::Tilde: consume(); return ExprNode::un(ExprNode::BNot, parseEP());
    case TokenKind::LogNot: consume(); return ExprNode::un(ExprNode::LNot, parseEP(), 1);
    case TokenKind::Amp: consume(); return ExprNode::red(ExprNode::RAnd, parseEP());
    case TokenKind::Pipe: consume(); return ExprNode::red(ExprNode::ROr, parseEP());
    case TokenKind::Caret: consume(); return ExprNode::red(ExprNode::RXor, parseEP());
    default: break;
    }
    auto tk = peek();
    switch (tk.kind) {
    case TokenKind::IntegerLiteral: case TokenKind::BaseLiteral: return parseN();
    case TokenKind::OpenParen: {
        consume(); auto e = parseE(); expect(TokenKind::CloseParen); return e;
    }
    case TokenKind::OpenBrace: {
        consume();
        if (peek().kind == TokenKind::CloseBrace) { consume(); return ExprNode::lit(0); }
        auto f = parseE();
        if (peek().kind == TokenKind::CloseBrace) { consume(); return f; }
        if (peek().kind == TokenKind::Comma) {
            std::vector<ExprPtr> items; items.push_back(std::move(f));
            while (peek().kind == TokenKind::Comma) { consume(); items.push_back(parseE()); }
            expect(TokenKind::CloseBrace);
            size_t tw = 0; for (auto& i : items) tw += i->width;
            return ExprNode::cat(std::move(items), tw);
        }
        consume(); auto v = parseE(); expect(TokenKind::CloseBrace); expect(TokenKind::CloseBrace);
        return ExprNode::rep(std::move(f), std::move(v), f->width * f->intVal);
    }
    default: {
        if (tk.kind != TokenKind::Identifier) { return ExprNode::lit(0); }
        auto n = consume().text;
        if (n[0] == '$') {
            std::vector<ExprPtr> args;
            if (peek().kind == TokenKind::OpenParen) {
                consume();
                while (peek().kind != TokenKind::CloseParen && peek().kind != TokenKind::Eof) {
                    args.push_back(parseE());
                    if (peek().kind == TokenKind::Comma) consume();
                }
                if (peek().kind == TokenKind::CloseParen) consume();
            }
            return ExprNode::sys(n, std::move(args));
        }
        auto e = ExprNode::ref(n);
        while (peek().kind == TokenKind::OpenBracket) {
            consume(); auto h = parseE();
            if (peek().kind == TokenKind::Colon) {
                consume(); auto l = parseE();
                size_t hi = (size_t)ec(h), lo = (size_t)ec(l);
                size_t w = (hi > lo) ? (hi - lo + 1) : (lo - hi + 1);
                e = ExprNode::slc(std::move(e), hi, lo, w);
            } else if (peek().kind == TokenKind::PlusColon) {
                consume(); auto w = parseE();
                size_t s = (size_t)ec(h), ww = (size_t)ec(w);
                e = ExprNode::slc(std::move(e), s + ww - 1, s, ww);
            } else {
                size_t idx = (size_t)ec(h);
                e = ExprNode::slc(std::move(e), idx, idx, 1);
            }
            expect(TokenKind::CloseBracket);
        }
        return e;
    }
    }
}

ExprPtr Parser::parseN() {
    auto tk = consume();
    if (tk.kind == TokenKind::BaseLiteral) {
        size_t w = 0; auto txt = tk.text; auto p = txt.find('\'');
        if (p != std::string::npos) { std::string ws = txt.substr(0, p); if (!ws.empty()) w = (size_t)std::stoul(ws); }
        return ExprNode::lit(tk.intVal, w > 0 ? w : 32);
    }
    uint64_t v = tk.intVal;
    size_t w = (v < 2) ? 1 : 0;
    if (w == 0) { uint64_t t = v; while (t) { t >>= 1; w++; } }
    return ExprNode::lit(v, w);
}
