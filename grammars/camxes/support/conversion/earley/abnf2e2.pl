#!/usr/bin/perl

$grammar_file="/tmp/abnf_grammar.$$";
$selmaho_file="/tmp/abnf_selmaho.$$";

#####
# First we split up the input into multiple files, as the main
# grammar and the selma'o need to be handled seperately.
#####

$grammar = 0;
$selmaho = 0;

open( GRAMMAR, ">$grammar_file" );
open( SELMAHO, ">$selmaho_file" );

while( <> )
{
    if( $grammar )
    {
	s/{/[/g;
	s/}/]/g;
	print GRAMMAR;
    }

    if( $selmaho )
    {
	print SELMAHO;
    }

    if( /; --- GRAMMAR ---/ )
    {
	$grammar = 1;
	$selmaho = 0;
    }

    if( /; --- SELMAHO ---/ )
    {
	$selmaho = 1;
	$grammar = 0;
    }
}

close( GRAMMAR );
close( SELMAHO );

$bison = `./abnf2bison.pl $grammar_file 2>&1`;

#print "!!!\n$bison\n!!!\n";

$done = 0;

#print "{";

for( split(/\n/, $bison) )
{
    # Fix the %token lines
#s/^\%token\s+(\S+)\s+(\S+)/$1 => [ [ $2 ] ]\,/;
    s/^\%token\s+(\S+)\s+(\S+)/$1: $2 /;

    # Remove all other % lines
    s/^\%.*//;

    # Fix "name:" (aka production) lines.
#s/^(.*):$/$1 => [ [/;

    # Fix ";" lines (end of production)
#s/^;$/] ],/;
s/^;$//;

    # Fix /* empty */ lines.
    s/.*\/\* empty \*\/.*/\t/;

    # Delete comments.
    s/.*\/\* (.*) \*\/.*//;

    # Fix | (alternation)
#s/\|/], [/g;

    # Quote all rule and production names.
#s/(?<=\s)(\w+)(?=\s)/\'$1\'/g;
#    s/^(\w+)(?=\s)/\'$1\'/g;
#    s/(?<=\s)(\w+)$/\'$1\'/g;

    # Insert commas.
#    s/' '/', '/g;

    if( m/#include/ )
    {
	$done = 1;
    }

    if( ! $done )
    {
	print $_."\n";
    }
};

open( SELMAHO, "<$selmaho_file" );

while( <SELMAHO> )
{
    # Delete comments.
    s/;.*//;

    # Fix "name = " (aka production) lines.
#s/^(.*)\s+=\s+/$1 => [ [/;
    s/^(.*)\s+=\s+/$1: /;

    # Fix / (alternation)
#s/\//], [/g;
    s/\//|/g;

    # Fix EOL if line not empty
#s/(?<=.)$/] ],/;

    # Quote all rule and production names.
#    s/(?<=\s)(\w+)(?=\s)/\'$1\'/g;
#    s/^(\w+)(?=\s)/\'$1\'/g;
#    s/(?<=\s)(\w+)$/\'$1\'/g;

    # Insert commas.
#    s/' '/', '/g;

    print $_."\n";
};

#print "};";

unlink( $grammar_file, $selmaho_file );
