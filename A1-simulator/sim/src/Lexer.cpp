#include "Lexer.h"
#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <sstream>

const std::unordered_map<std::string, TokenKind> Lexer::keywords = {
    {"module", TokenKind::Module},
    {"endmodule", TokenKind::Endmodule},
    {"input", TokenKind::Input},
    {"output", TokenKind::Output},
    {"inout", TokenKind::Inout},
    {"wire", TokenKind::Wire},
    {"reg", TokenKind::Reg},
    {"integer", TokenKind::Integer},
    {"assign", TokenKind::Assign},
    {"always", TokenKind::Always},
    {"initial", TokenKind::Initial},
    {"begin", TokenKind::Begin},
    {"end", TokenKind::End},
    {"if", TokenKind::If},
    {"else", TokenKind::Else},
    {"for", TokenKind::For},
    {"case", TokenKind::Case},
    {"endcase", TokenKind::Endcase},
    {"default", TokenKind::Default},
    {"generate", TokenKind::Generate},
    {"endgenerate", TokenKind::Endgenerate},
    {"genvar", TokenKind::Genvar},
    {"parameter", TokenKind::Parameter},
    {"localparam", TokenKind::Localparam},
    {"posedge", TokenKind::PosEdge},
    {"negedge", TokenKind::NegEdge},
    {"or", TokenKind::Or},
    {"signed", TokenKind::Signed},
    {"defparam", TokenKind::Defparam},
    {"`define", TokenKind::Define},
    {"`include", TokenKind::Incl},
    {"`ifdef", TokenKind::Ifdef_kw},
    {"`ifndef", TokenKind::Ifndef_kw},
    {"`else", TokenKind::Else_kw},
    {"`endif", TokenKind::Endif_kw},
    {"`undef", TokenKind::Undef_kw},
    {"`default_nettype", TokenKind::DefaultNettype_kw},
    {"`resetall", TokenKind::Resetall_kw},
    {"`timescale", TokenKind::Timescale_kw},
    {"always_comb", TokenKind::AlwaysComb},
    {"always_ff", TokenKind::AlwaysFF},
    {"always_latch", TokenKind::AlwaysLatch},
};

const std::unordered_map<std::string, TokenKind> Lexer::sysFuncs = {
    {"$display", TokenKind::SysDisplay},
    {"$fopen", TokenKind::SysFopen},
    {"$fgets", TokenKind::SysFgets},
    {"$fscanf", TokenKind::SysFscanf},
    {"$fdisplay", TokenKind::SysFdisplay},
    {"$fclose", TokenKind::SysFclose},
    {"$readmemh", TokenKind::SysReadmemh},
    {"$finish", TokenKind::SysFinish},
    {"$time", TokenKind::SysTime},
    {"$dumpvars", TokenKind::SysDumpvars},
    {"$clog2", TokenKind::SysClog2},
    {"$fwrite", TokenKind::SysFwrite},
    {"$fread", TokenKind::SysFread},
    {"$random", TokenKind::SysRandom},
    {"$monitor", TokenKind::SysMonitor},
    {"$strobe", TokenKind::SysStrobe},
};

Lexer::Lexer(const std::string& source) : src(source), pos(0) {
    // ensure null termination
    if (src.empty() || src.back() != '\0') src.push_back('\0');
}

void Lexer::setSource(const std::string& source) {
    src = source;
    if (src.empty() || src.back() != '\0') src.push_back('\0');
    pos = 0;
    lookahead.clear();
}

char Lexer::cur() const { return pos < src.size() ? src[pos] : '\0'; }
char Lexer::peekc(size_t a) const { return pos + a < src.size() ? src[pos + a] : '\0'; }
void Lexer::advance(size_t n) { pos += n; }
bool Lexer::isEof() const { return pos >= src.size() || src[pos] == '\0'; }

std::string Lexer::getSourceAround(size_t p, size_t len) const {
    size_t start = (p > len) ? p - len : 0;
    size_t end = std::min(p + len, src.size());
    return src.substr(start, end - start);
}

void Lexer::skipLine() {
    while (!isEof() && cur() != '\n') advance();
    if (cur() == '\n') advance();
}

void Lexer::skipBlockComment() {
    advance(2); // skip /*
    while (!isEof()) {
        if (cur() == '*' && peekc() == '/') { advance(2); return; }
        advance();
    }
}

Token Lexer::lexString() {
    size_t start = pos;
    advance(); // skip "
    std::string val;
    while (!isEof() && cur() != '"') {
        if (cur() == '\\') { advance(); if (!isEof()) { val += cur(); advance(); } }
        else { val += cur(); advance(); }
    }
    if (cur() == '"') advance();
    return Token(TokenKind::StringLiteral, val);
}

uint64_t Lexer::parseNumber(const std::string& s, int base) const {
    uint64_t r = 0;
    for (char c : s) {
        if (c == '_') continue;
        r *= base;
        if (c >= '0' && c <= '9') r += (c - '0');
        else if (c >= 'a' && c <= 'f') r += (c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') r += (c - 'A' + 10);
    }
    return r;
}

Token Lexer::lexNumber() {
    size_t start = pos;
    // Check if it's a base literal like 8'hAB or 32'd5
    std::string digits;
    while (std::isdigit(cur()) || cur() == '_') {
        digits += cur(); advance();
    }
    // Could be a base literal: <size>'<base><value>
    if (cur() == '\'') {
        advance();
        char baseChar = std::tolower(cur());
        int base = 10;
        if (baseChar == 'h') base = 16;
        else if (baseChar == 'd') base = 10;
        else if (baseChar == 'b') base = 2;
        else if (baseChar == 'o') base = 8;
        else { // unsized 'h, 'd, etc
            // Could also be just 'b' etc. -- re-read
        }
        advance();
        // Skip optional s (signed)
        if (cur() == 's' || cur() == 'S') advance();
        std::string valStr;
        while (std::isxdigit(cur()) || cur() == '_' || cur() == 'x' || cur() == 'X' || cur() == 'z' || cur() == 'Z') {
            valStr += cur(); advance();
        }
        uint64_t intVal = 0;
        if (!valStr.empty() && valStr.find_first_of("xXzZ") == std::string::npos)
            intVal = parseNumber(valStr, base);
        Token t(TokenKind::BaseLiteral, src.substr(start, pos - start));
        t.intVal = intVal;
        return t;
    }

    // Decimal with possible real
    if (cur() == '.') {
        advance();
        while (std::isdigit(cur()) || cur() == '_') { digits += cur(); advance(); }
        Token t(TokenKind::RealLiteral, src.substr(start, pos - start));
        t.intVal = (uint64_t)std::stod(t.text);
        return t;
    }

    // Check for time notation
    if (cur() == 's' || cur() == 'n' || cur() == 'p' || cur() == 'f') {
        // Skip time unit suffix
        advance();
    }

    Token t(TokenKind::IntegerLiteral, digits);
    t.intVal = parseNumber(digits, 10);
    return t;
}

Token Lexer::lexIdentifierOrKeyword() {
    size_t start = pos;
    while (std::isalnum(cur()) || cur() == '_' || cur() == '$') advance();
    std::string word = src.substr(start, pos - start);

    // Check system functions
    if (!word.empty() && word[0] == '$') {
        auto it = sysFuncs.find(word);
        if (it != sysFuncs.end())
            return Token(it->second, word);
        return Token(TokenKind::Identifier, word);
    }

    auto it = keywords.find(word);
    if (it != keywords.end())
        return Token(it->second, word);
    return Token(TokenKind::Identifier, word);
}

Token Lexer::lexOperator() {
    size_t start = pos;
    char c = cur(); advance();

    switch (c) {
    case ';': return Token(TokenKind::Semicolon, ";");
    case ',': return Token(TokenKind::Comma, ",");
    case '.': return Token(TokenKind::Dot, ".");
    case ':': return Token(TokenKind::Colon, ":");
    case '(': return Token(TokenKind::OpenParen, "(");
    case ')': return Token(TokenKind::CloseParen, ")");
    case '[': return Token(TokenKind::OpenBracket, "[");
    case ']': return Token(TokenKind::CloseBracket, "]");
    case '{': return Token(TokenKind::OpenBrace, "{");
    case '}': return Token(TokenKind::CloseBrace, "}");
    case '#': return Token(TokenKind::Hash, "#");
    case '@': return Token(TokenKind::At, "@");
    case '?': return Token(TokenKind::Question, "?");
    case '~': return Token(TokenKind::Tilde, "~");
    case '*':
        if (cur() == '*') { advance(); return Token(TokenKind::DoubleStar, "**"); }
        if (cur() == ')') { advance(); return Token(TokenKind::Star, "*)"); }
        return Token(TokenKind::Star_op, "*");
    case '/':
        if (cur() == '/') { skipLine(); return next(); }
        if (cur() == '*') { skipBlockComment(); return next(); }
        return Token(TokenKind::Slash, "/");
    case '%': return Token(TokenKind::Percent, "%");
    case '+':
        if (cur() == ':') { advance(); return Token(TokenKind::PlusColon, "+:"); }
        if (cur() == '=') { advance(); return Token(TokenKind::PlusAssign, "+="); }
        return Token(TokenKind::Plus, "+");
    case '-':
        if (cur() == ':') { advance(); return Token(TokenKind::MinusColon, "-:"); }
        if (cur() == '=') { advance(); return Token(TokenKind::MinusAssign, "-="); }
        if (cur() == '>') { advance(); return Token(TokenKind::ArithShiftRight, "->"); }
        return Token(TokenKind::Minus, "-");

    case '&':
        if (cur() == '&') { advance(); return Token(TokenKind::LogAnd, "&&"); }
        return Token(TokenKind::Amp, "&");
    case '|':
        if (cur() == '|') { advance(); return Token(TokenKind::LogOr, "||"); }
        return Token(TokenKind::Pipe, "|");
    case '^': return Token(TokenKind::Caret, "^");
    case '!':
        if (cur() == '=') { advance(); return Token(TokenKind::Neq, "!="); }
        return Token(TokenKind::LogNot, "!");
    case '<':
        if (cur() == '=') { advance(); return Token(TokenKind::Le, "<="); }
        if (cur() == '<') { advance(); return Token(TokenKind::ShiftLeft, "<<"); }
        return Token(TokenKind::Lt, "<");
    case '>':
        if (cur() == '=') { advance(); return Token(TokenKind::Ge, ">="); }
        if (cur() == '>') { advance(); return Token(TokenKind::ShiftRight, ">>"); }
        return Token(TokenKind::Gt, ">");
    case '=':
        if (cur() == '=') { advance(); return Token(TokenKind::Eq, "=="); }
        if (cur() == '>') { advance(); return Token(TokenKind::ArithShiftRight, "=>"); }
        return Token(TokenKind::AssignOp, "=");
    case '\'':
        if (cur() == '{') { advance(); return Token(TokenKind::OpenBrace, "'{"); } // actually tick+brace
        // Verilog base literal: 'b, 'h, 'd, 'o
        return Token(TokenKind::Invalid, "'");
    }
    return Token(TokenKind::Invalid, std::string(1, c));
}

Token Lexer::lexPreprocessor() {
    size_t start = pos;
    advance(); // skip `
    std::string dir;
    while (std::isalpha(cur()) || cur() == '_') { dir += cur(); advance(); }
    std::string fullDir = "`" + dir;

    if (dir == "include") {
        // Skip whitespace
        while (cur() == ' ' || cur() == '\t') advance();
        std::string filepath;
        if (cur() == '"') {
            advance();
            while (!isEof() && cur() != '"') { filepath += cur(); advance(); }
            if (cur() == '"') advance();
        } else if (cur() == '<') {
            advance();
            while (!isEof() && cur() != '>') { filepath += cur(); advance(); }
            if (cur() == '>') advance();
        }
        Token t(TokenKind::Incl, filepath);
        return t;
    }
    if (dir == "define") {
        while (cur() == ' ' || cur() == '\t') advance();
        std::string macroName;
        while (std::isalnum(cur()) || cur() == '_') { macroName += cur(); advance(); }
        while (cur() == ' ' || cur() == '\t') advance();
        std::string macroValue;
        while (!isEof() && cur() != '\n' && cur() != '\r') { macroValue += cur(); advance(); }
        Token t(TokenKind::Define, macroName);
        t.text = macroName + " " + macroValue;
        return t;
    }
    if (dir == "timescale") {
        std::string rest;
        while (!isEof() && cur() != '\n' && cur() != '\r') { rest += cur(); advance(); }
        Token t(TokenKind::Timescale_kw, rest);
        return t;
    }
    if (dir == "default_nettype" || dir == "resetall") {
        std::string rest;
        while (!isEof() && cur() != '\n' && cur() != '\r') { rest += cur(); advance(); }
        return Token(TokenKind::Identifier, "`" + dir + rest);
    }
    if (dir == "ifdef" || dir == "ifndef") {
        while (cur() == ' ' || cur() == '\t') advance();
        std::string ident;
        while (std::isalnum(cur()) || cur() == '_') { ident += cur(); advance(); }
        return Token(dir == "ifdef" ? TokenKind::Ifdef_kw : TokenKind::Ifndef_kw, ident);
    }
    if (dir == "endif") {
        return Token(TokenKind::Endif_kw, "`endif");
    }
    if (dir == "else") {
        while (cur() == ' ' || cur() == '\t') advance();
        if (cur() == 'i') { // `elsif
            std::string rest;
            while (std::isalnum(cur()) || cur() == '_') { rest += cur(); advance(); }
        }
        return Token(TokenKind::Else_kw, "`else");
    }
    if (dir == "undef") {
        while (cur() == ' ' || cur() == '\t') advance();
        std::string ident;
        while (std::isalnum(cur()) || cur() == '_') { ident += cur(); advance(); }
        return Token(TokenKind::Undef_kw, ident);
    }

    return Token(TokenKind::Invalid, fullDir);
}

Token Lexer::peek(size_t ahead) {
    while (lookahead.size() <= ahead) {
        lookahead.push_back(next());
    }
    return lookahead[ahead];
}

Token Lexer::consume() {
    if (!lookahead.empty()) {
        Token t = lookahead.front();
        lookahead.erase(lookahead.begin());
        return t;
    }
    return lexToken();
}

bool Lexer::expect(TokenKind k) {
    if (peek().kind == k) { consume(); return true; }
    return false;
}

Token Lexer::lexToken() {
    // Skip whitespace
    while (!isEof() && (cur() == ' ' || cur() == '\t' || cur() == '\n' || cur() == '\r'))
        advance();

    if (isEof()) return Token(TokenKind::Eof, "");

    char c = cur();
    size_t startPos = pos;

    // Preprocessor directive
    if (c == '`') return lexPreprocessor();

    // Number or base literal
    if (std::isdigit(c)) return lexNumber();

    // Identifier, keyword, or system function
    if (std::isalpha(c) || c == '_' || c == '$') return lexIdentifierOrKeyword();

    // String literal
    if (c == '"') return lexString();

    // Operators and symbols
    return lexOperator();
}
