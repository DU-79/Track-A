#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include <unordered_map>

enum class TokenKind : uint8_t {
    Eof, Invalid,
    Identifier, IntegerLiteral, RealLiteral, StringLiteral,
    BaseLiteral, // e.g. 8'hAB
    Timescale,

    // Keywords
    Module, Endmodule, Input, Output, Inout, Wire, Reg, Integer,
    Assign, Always, Initial, Begin, End, If, Else, For, Case,
    Endcase, Default, Generate, Endgenerate, Genvar, Parameter,
    Localparam, PosEdge, NegEdge, Or, 
    And, Or_kw, Nand, Nor, Xor, Xnor,
    Not, Real, Time, Signed, 
    While, Forever, Repeat, Wait, 
    Function, Endfunction, Task, Endtask,
    Specify, Endspecific, Primitive, Endprimitive,
    Cmos, Rcmos, Nmos, Rpmos, Pullup, Pulldown,
    Ror, RAnd,
    Tri, Tri0, Tri1, TriAnd, TriOr, TriReg,
    Supply0, Supply1, Wand, Wor,
    Macromodule, 
    Defparam,
    Edge, 
    Incl, // `include
    Define, // `define
    Ifdef_kw, Ifndef_kw, Else_kw, Endif_kw,
    Undef_kw, 
    DefaultNettype_kw, 
    Resetall_kw,
    Timescale_kw, // `timescale
    // System functions
    SysDisplay, SysFopen, SysFgets, SysFscanf, SysFdisplay,
    SysFclose, SysReadmemh, SysFinish, SysTime, SysDumpvars,
    SysFwrite, SysFstrobe, SysMonitor, SysClog2, SysFread,
    SysRandom, SysStrobe, SysWrite, SysOnehot, SysOnehot0,
    SysFflush, SysSformat, SysSformatf,
    // Additional keywords
    AlwaysComb, AlwaysFF, AlwaysLatch,
    Star,

    // Symbols
    Semicolon, Comma, Dot, Colon, OpenParen, CloseParen,
    OpenBrace, CloseBrace, OpenBracket, CloseBracket,
    Hash, At, Question, Tilde,
    Plus, Minus, Star_op, Slash, Percent,
    Amp, Pipe, Caret,
    Eq, Neq, Lt, Gt, Le, Ge,
    LogAnd, LogOr, LogNot,
    ShiftLeft, ShiftRight, ArithShiftRight,
    AssignOp, PlusAssign, MinusAssign,
    NBAOp, // <=
    DoubleStar, // **
    DoubleLeft, DoubleRight,
    TripleAnd,
    MinusColon,
    PlusColon,
    ColonSlash,
};

struct Token {
    TokenKind kind;
    std::string text;
    int64_t intVal;
    size_t pos;
    size_t len;

    Token() : kind(TokenKind::Invalid), intVal(0), pos(0), len(0) {}
    Token(TokenKind k, std::string t = "")
        : kind(k), text(std::move(t)), intVal(0), pos(0), len(0) {}
};

class Lexer final {
public:
    explicit Lexer(const std::string& source);
    Token next() { return lexToken(); }
    Token peek(size_t ahead = 0);
    Token consume();
    Token lexToken();
    bool expect(TokenKind k);
    void setSource(const std::string& source);
    std::string getSourceAround(size_t pos, size_t len = 40) const;

private:
    std::string src;
    size_t pos;
    std::vector<Token> lookahead;
    char cur() const;
    char peekc(size_t a = 0) const;
    void advance(size_t n = 1);
    bool isEof() const;
    void skipLine();
    void skipBlockComment();
    Token lexString();
    Token lexNumber();
    Token lexIdentifierOrKeyword();
    Token lexOperator();
    Token lexPreprocessor();
    Token lexBaseLiteral();
    uint64_t parseNumber(const std::string& s, int base) const;

    static const std::unordered_map<std::string, TokenKind> keywords;
    static const std::unordered_map<std::string, TokenKind> sysFuncs;
};
