#!/usr/bin/perl

while(<STDIN>)
{
    if( /^;/ ) # If comment
    {
	print;
	next;
    }

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

    # 1* and *, no parens
    s{1\*([a-zA-Z-0-9_-]+)}{$1\+}xg;
    s{\*([a-zA-Z-0-9_-]+)}{$1\*}xg;

    # Handle 1* and * which requires dealing with the possibility of 
    # balanced (...) pairs.
    s{1\*($reparen)}{$1\+}xg;
    s{\*($reparen)}{$1\*}xg;

    # Convert [...] to (...)?
    s{$resq}{\($1\)\?}xg;
    s{$resq}{\($1\)\?}xg;
    s{$resq}{\($1\)\?}xg;

    # Convert {...} to (...)?
    s/{([^}]*)}/($1)?/g;

    # Add change = to <-
    s/^(\S+) = /\1 <- /;

    print;
}
