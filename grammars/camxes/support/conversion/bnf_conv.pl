#!/usr/bin/perl

open( BNF, "<bnf.txt" );

while(<BNF>)
{
    # Make sure there's a space between # and everything else.
    s{([^ \t])#}{\1 #};

    # Turn // into {}
    s{/([^/]*)/}{\{\1\}}g;

    # Turn | into /
    tr{|}{/};

    # Turn # into *free
    s{\#}{*free}g;

    # Match balanced square brackets
    $resq = qr{
	\[
	(
	    (?:
	     (?> [^][]+ )    # Non-parens without backtracking
	     |
	     (??{ $resq })     # Group with matching parens
	    )*
	)
	\]
    }x;

    # Match balanced parens
    $reparen = qr{
	\(
	    (?:
	     (?> [^()]+ )    # Non-parens without backtracking
	     |
	     (??{ $reparen })     # Group with matching parens
	    )*
	\)
    }x;

    # Handle ..., which requires dealing with the possibility of 
    # balanced [...] and (...) pairs.
    s{($reparen)\s+\.\.\.}{1*$1}xg;
    # 1*[...] == *(...), by the way.
    s{$resq\s+\.\.\.}{*\($1\)}xg;
    s{([-A-Za-z0-9]+)\s+\.\.\.}{1*$1}g;

    # (A & B) => (A / B / A B)
    s{\(([^(&)]+)\s+&\s+([^&)]+)\)}{($1 / $2 / $1 $2)};
    # 1*(A) & B => ((A) / B / (A) B)
    s{(1\*$reparen)\s+&\s+([-A-Za-z0-9]+)}{($1 / $2 / $1 $2)};
    # (A) & B => ((A) / B / (A) B)
    s{($reparen)\s+&\s+([-A-Za-z0-9]+)}{($1 / $2 / $1 $2)};

    # WARNING: Not so sure about this step.
    # A & B & C &D =>
    # A [B] [C] [D] / [A] B [C] [D] / [A] [B] C [D] / [A] [B] [C] D
    s{=\s+([^&]+)\s+&\s+([^&]+)\s+&\s+([^&]+)\s+&\s+([^&\n]+)$}
    {= $1 [$2] [$3] [$4] / [$1] $2 [$3] [$4] / [$1] [$2] $3 [$4] / [$1] [$2] [$3] $4};

    print;
}
