#!/usr/bin/perl
# *****************************************************************************
# 
# $Id: abnfchk,v 1.26 1999/09/18 23:08:16 bfb Exp bfb $
# 
# Copyright (C) 1999, 2000, Inet Technologies, Inc. <www.inet.com>
#
# Written by: Brian Bidulock <brian.bidulock@inet.com>
# 
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 675 Mass Ave, Cambridge, MA 02139, USA.
# 
# *****************************************************************************

eval 'exec /usr/bin/perl -S $0 ${1+"$@"}'
	if $running_under_some_shell;

$progname = $0;

if ($progname=~/^(.+\/)*sbnfchk/   ) { $gabnf  = 1; }
if ($progname=~/^(.+\/)*abnfchk/   ) { $gabnf  = 1; }
if ($progname=~/^(.+\/)*abnf2asn/  ) { $gasn   = 1; }
if ($progname=~/^(.+\/)*abnf2html/ ) { $ghtml  = 1; }
if ($progname=~/^(.+\/)*abnf2bison/) { $gbison = 1; }
if ($progname=~/^(.+\/)*abnf2flex/ ) { $gflex  = 1; }

$numbers  = 0;
$debug    = 0;
$trace    = 0;
$verbose  = 0;
$crossref = 0;
$comments = 0;
$warnings = 0;

while ($ARGV[0] =~ /^-/) {
    $_ = shift;
  last if /^--/;
    if (/^-h/) { usage();       exit; }
    if (/^-n/) { $numbers  = 1; next; }
    if (/^-d/) { $debug    = 1; next; }
    if (/^-t/) { $trace    = 1; next; }
    if (/^-v/) { $verbose  = 1; next; }
    if (/^-x/) { $crossref = 1; next; }
    if (/^-c/) { $comments = 1; next; }
    if (/^-w/) { $warnings = 1; next; }
    if (/^-r/) { $warnrefs = 1; next; }
    if (/^-f(.*)/) { if ($1) { $infile = $1; } else { $infile = shift; } next; }
    if (/^-o(.*)/) { if ($1) { $outfile = $1; } else { $outfile = shift; } next; }
    usage();
    die "I don't recognize this switch: $_\\n";
}
if ($_=shift) { $infile = $_; }
if ($_=shift) { $outfile = $_; }

sub usage {
    print STDERR "Usage:  $0 ".'[-dtvxcn] [ [-f] infile [ [-o] outfile ] ]'."\n\n";
    print STDERR "  -h  - this help message\n";
    print STDERR "  -d  - turn on debug mode\n";
    print STDERR "  -t  - turn on trace mode (lots of info)\n";
    print STDERR "  -v  - turn on verbose mode (lots of info)\n";
    print STDERR "  -x  - report crossreferences in output\n" if($gabnf||$gasn);
    print STDERR "  -n  - number productions in output\n" if ($ghtml);
    print STDERR "  -c  - include ABNF comments in output\n" if ($ghtml);
    print STDERR "  -w  - include warnings for mismatched case\n" if ($ghtml);
    print STDERR "  -r  - include warnings for orphan references\n" if ($ghtml);
    print STDERR "  [-f] infile  -  input file (default stdin)\n";
    print STDERR "  [-o] outfile - output file (default stdout)\n";
    print STDERR "\n$0: ";
    print STDERR "Syntax checks and pretty-prints ABNF\n"   if ($gabnf);
    print STDERR "Converts ABNF to ASN (no too well)\n"     if ($gasn);
    print STDERR "Provides HTML of ABNF syntax\n"           if ($ghtml);
    print STDERR "Provides BISON parser output for ABNF\n"  if ($gbison);
    print STDERR "Provides FLEX analyzer output for ABNF\n" if ($gflex);
}

$\ = "\n";		# add new-line to print
$* = 0;         # do multiline matching
#undef $/;       # read in whole file

if ($infile) {
    open(INFILEH,"<$infile") || die "can't open $infile for input";
    $ifh = \*INFILEH;
} else {
    $ifh = \*STDIN;
}

if ($outfile) {
    open(OUTFILEH,">$outfile") || die "can't open $outfile for output";
    select OUTFILEH;
} else {
    select STDOUT;
}

$rulemax = 0;

# =======================================
    package Abnf;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    my $o;
    main->getlines($line);
    if ($o = RuleList->new($line)) {
        push @{$self->{rulelist}}, $o;
        $::error = '';
        $::errdep = 0;
        main->getlines($line);
        while ($o = RuleList->new($line)) {
            push @{$self->{rulelist}}, $o;
            $::error = '';
            $::errdep = 0;
            main->getlines($line);
        }
        unless ($::done) {
            print "SYNTAX ERROR (LINE $::lineno) NEAR: '$::error'";
            return 0;
        }
    }
    $_[0] = $line;
    return $self;
}

sub abnf {
    my $self = shift;
    print ';@@ ABNFCHK $Revision: 1.26 $';
    print ';@@ Copyright (C) 1999, 2000, Brian F. G. Bidulock';
    print ';@@ <bidulock@dallas.net>';
    print '';
    my $file = $::infile;
    $file = "(standard input)" unless ($file);
    print ";@@ Input file: <$file>";
    my $d = `date`;  chomp $d;
    printf ';@@ Date: '.$d;
    my $s; foreach $s (@{$self->{rulelist}}) { $s->abnf(); }
    print '';
    print '';
    print '';
    print ';@@ end of productions';
    if ($::crossref) {
        print ";@@ *******************************";
        my $e;
        my $i = 0;
        foreach $e (keys %::caserefs) { $i++;
            unless ($::casedefs{$e}) {
                print ";@@ UNDEFINED REFERENCE: $e";
            }
        }
        print ";@@ THERE ARE $i REFERENCES.";
        $i = 0;
        foreach $e (keys %::casedefs) { $i++;
            if ($::casedefs{$e}>1) {
                print ";@@ DEFINITION $e DEFINED $::casedefs{$e} TIMES!";
            }
            unless ($::caserefs{$e}) {
                print ";@@ UNREFERENCED DEFINITION: $e";
            }
        }
        print ";@@ THERE ARE $i DEFINITIONS.";
    }
    print '';
    print '';
}

sub asn1 {
    my $self = shift;
    print '--@@ ABNF2ASN $Revision: 1.26 $';
    print '--@@ Copyright (C), 1999 Brian F. G. Bidulock';
    print '--@@ <bidulock@dallas.net>';
    print '';
    my $f = $::infile; $f = "(standard input)" unless ($f);
    print "--@@ Input file: <$f>";
    my $s; foreach $s (@{$self->{rulelist}}) { $s->asn1(); }
    print '';
    print '';
    print '--@@ end of syntax description';
}

sub html {
    my $self = shift;
    my $e;
    my $i;
    my $f = $::infile;
    print '<HTML>';
    print '<HEAD>';
    printf '<TITLE>ABNF Specification';
    printf ' for &lt;'.$f.'&gt;' if ($f);
    print '</TITLE>';
    print '</HEAD>';
    print '<BODY>';
    printf '<H1>HTML Version of ABNF';
    printf ' for <tt>&lt;'.$f.'&gt;</tt>' if ($f);
    print  '</H1>';

    if (open(HEADER,"<.html.header")) {
        my $line;
        my $d = `date`; chomp $d;
        my $r = '$Revision: 1.26 $';
        while ($line=<HEADER>) { chop $line;
            $line=~s/\%f/$f/;
            $line=~s/\%p/\U$::progname\E/;
            $line=~s/\%r/$r/;
            $line=~s/\%d/$d/;
            print $line;
        }
    } else {
        print '<P>This HTML version of ABNF is automatically generated using ';
        print 'the <b>abnf2html</b> $Revision: 1.26 $ tool provided by ';
        print '<a href="http://www.inet.com/">Inet Technologies, Inc.</a> ';
        print 'written by <a href="mailto:brian.bidulock@inet.com">Brian ';
        print 'Bidulock</a>.';
        print 'The protocol syntax is presented in ABNF according to RFC 2234 ';
        print 'and RFC 822.';
        print 'This version of ABNF is for informational purposes only.  It ';
        print 'is intended as a tool to help read the ABNF. ';
        print 'Errors may have been introduced in translating to HTML.</P>';
        print  '';
        if ($f) {
        print 'This ABNF browser was generated from file &lt;'.$f.'&gt;';
        print ' on '.`date`.'.'; }
        print '</P>';
        print '<P>This file consists of:';
        print '<UL>';
        print '<LI><A HREF="#Spec">ABNF Specification</a>,';
        print '<LI><A HREF="#Xref">Symbol Cross Reference Table</a>, and,';
        print '<LI><A HREF="#Help">General Directions</a>.';
        print '</UL>';
    }
    print '<A NAME="Spec"><H2>ABNF Specification</H2></a>';
    print '<P>The productions for the ABNF specification are provided below.';
    print '<P><TABLE CELLSPACING=1 BORDER=0 CELLPADDING=1>';
    print '<CAPTION><B><I>ABNF Productions</i></b></CAPTION>';
    printf '<TR BGCOLOR="yellow" VALIGN=middle>';
    printf '<TH BGCOLOR="yellow" ALIGN=CENTER>No.</TH>' if ($::numbers);
    print  '<TH COLSPAN=2 BGCOLOR="yellow" ALIGN=CENTER>Rule Name</TH><TH BGCOLOR="yellow" ALIGN=CENTER>Production or Comment</TH></TR>';
    my $s; foreach $s (@{$self->{rulelist}}) { $s->html(); }
    print '</TABLE>';
    print '<A NAME="Xref"><H2>Symbol Cross Reference List</H2></A>';
    printf '<P>Following is a cross-reference list for the ABNF.  On the left ';
    printf 'are references to productions, on the right are links to the rules in ';
    print 'which those productions are referenced.';
    print '<TABLE CELLSPACING=1 BORDER=1 CELLPADDING=1>';
    print '<CAPTION><BR><B><I>Symbol Cross-Reference Table</i></b></CAPTION>';
    print '<TR><TH BGCOLOR="yellow" ALIGN=LEFT><B>Reference</B></TH><TH BGCOLOR="yellow" ALIGN=LEFT><B>Productions which Reference this Symbol</B></TH></TR>';
    if ($::warnrefs) {
        foreach $e (keys %::defs) {
            unless ($::refs{$e}) {
                $::reflist{$e} = 0;
            }
        }
    }
    foreach $e (sort keys %::reflist) {
        printf '<TR VALIGN=TOP><TD><A NAME="Xref.'.$e.'">';
        if ($::casedefs{lc $e}) {
            printf '<A HREF="#'.lc($e).'">';
            if ($::defs{$e} or not $::warnings) {
                printf $e;
            } else {
                printf '<FONT COLOR="orange">'.$e.'</FONT>';
            }
            printf '</A>';
        } else {
            if ($::warnrefs) {
                printf '<A HREF="#RedReference">';
                printf '<FONT COLOR="red">'.$e.' (undefined)</FONT>';
                printf '</A>';
            } else {
                printf '<FONT COLOR="blue">'.$e.'</FONT>';
            }
        }
        print '</A></TD>';
        printf '<TD>';
        if ($::reflist{$e}) {
            for ($i=0;$i<$::reflist{$e};$i++) {
                printf ', ' if ($i);
                printf '<A HREF="#';
                printf lc($::deflist{$e}[$i]);
                printf '">';
                printf $::deflist{$e}[$i];
                printf '</A>';
            }
        } else {
            if ($::caserefs{lc $e} and $::warnings) {
                printf '<A HREF="#OrangeRuleName"><FONT COLOR="orange">(No references!)</FONT></A>';
            } else {
                printf '<A HREF="#RedRuleName"><FONT COLOR="red">(No references!)</FONT></A>';
            }
        }
        print '</TD></TR>';
    }
    print '</TABLE>';
    print '<A NAME="Help"><H2>General Directions</H2></A>';
    print '<H4>Rule-Names</H4>';
    print '<UL>';
    printf '<LI>Clicking on the rule-name will move you to the list of ';
    print 'references to the selected rule-name.';
    if ($::warnrefs) {
        print '<LI>';
        printf '<A NAME="RedRuleName">';
        printf 'Rule-names which are shown in ';
        printf '<FONT COLOR="red">red</FONT> cannot be selected because they are never ';
        printf 'referenced in the specification.  If a rule-name other than the root ';
        printf 'rule-name is shown in <FONT COLOR="red">red</FONT>, the ';
        printf 'specification is <i>not</i> in error, but there are unreferenced (redundant) ';
        printf 'productions in the specification.';
        print '</A>';
    }
    if ($::warnings) {
        print '<LI>';
        printf '<A NAME="OrangeRuleName">';
        printf 'Rule-names which are shown in ';
        printf '<FONT COLOR="orange">orange</FONT> cannot be selected because they are never ';
        printf 'referenced in the specification.  If a rule-name other than the root ';
        printf 'rule-name is shown in <FONT COLOR="orange">orange</FONT>, the ';
        printf 'specification is <i>not</i> in error, but there are unreferenced (redundant) ';
        printf 'productions in the specification.  ';
        printf 'An error may exist due to capitalization because a reference ';
        printf 'exists which differs from the rule-name only in capitalization.';
        print '</A>';
    }
    print '</UL>';
    print '<H4>References</H4>';
    print '<UL>';
    printf '<LI>Clicking on references in the production will move you to the ';
    print 'production with the rule-name selected.';
    if ($::warnrefs) {
        printf '<LI>';
        printf '<A NAME="RedReference">';
        printf 'References which are ';
        printf 'shown in <FONT COLOR="red">red</FONT> cannot be selected because ';
        printf 'they are never defined in the specification.  If there are ';
        printf 'references shown in <FONT COLOR="red">red</FONT> then the ';
        printf 'specification is either <i>incomplete</i> or <i>in error</i>.';
        print '</A>';
    }
    if ($::warnings) {
        print '<LI>';
        printf '<A NAME="OrangeReference">';
        printf '<P>References which are ';
        printf 'shown in <FONT COLOR="orange">orange</FONT> cannot be selected because ';
        printf 'they are never defined in the specification.  If there are ';
        printf 'references shown in <FONT COLOR="orange">orange</FONT> then the ';
        print 'specification is either <i>incomplete</i> or <i>in error</i>.  ';
        printf 'The error is likely due to capitalization because a rule-name ';
        printf 'exists which differs from the reference only in capitalization.';
        print '</A>';
    }
    print '</UL>';
    if (open(FOOTER,"<.html.footer")) {
        my $line;
        my $d = `date`; chomp $d;
        my $r = '$Revision: 1.26 $';
        while ($line=<FOOTER>) { chop $line;
            $line=~s/\%f/$f/;
            $line=~s/\%p/\U$::progname\E/;
            $line=~s/\%r/$r/;
            $line=~s/\%d/$d/;
            print $line;
        }
    }
    print '</BODY>';
    print '</HTML>';
}

sub bison {
    my $self = shift;
    if ($::trace) { printf '/* '.ref($self).' */'; }
#   print '%{';
#   print '/* C DECLARATIONS */';
#   print '%}';
#   print '';
    print '/* BISON DECLARATIONS */';
    print '';
    print '%token_table';
    print '';
    my $s; foreach $s (@{$self->{rulelist}}) { $s->bisondeclare(); }
    print '';
    print '%%';
    print '/* GRAMMAR RULES */';
    print '';
    my $s; foreach $s (@{$self->{rulelist}}) { $s->bisongrammar(); }
    print '%%';
    print '';
    print '/* ADDITIONAL C CODE */';
    print '';
    print '#include <ctype.h>';
    print '#include <stdio.h>';
    print '';
    print 'yyerror(s)';
    print '    char *s;';
    print '{';
    print '    printf("%s\n",s);';
    print '}';
    print '';
    print 'yylex()';
    print '{';
    print '    int c;';
    print '    c = getchar();';
    print '    if (c == EOF)';
    print '        return 0;';
    print '    return c;';
    print '}';
    print '';
    print 'main()';
    print '{';
    print '    yydebug = 1;';
    print '    yyparse();';
    print '}';
    print '';
}

sub flex {
    my $self = shift;
    if ($::trace) { printf '/* '.ref($self).' */'; }
    print '%{';
    print '/* C DECLARATIONS */';
    print '';
    print '#include "tmp.tab.h"';
    print '';
    print '%}';
    print '/* FLEX DECLARATIONS */';
    print '';
    print '%option warn';
    print '%option debug';
    print '%option verbose';
    print '%option perf-report';
    print '%option caseless';
    print '%option 7bit'; 
    print '%option yylineno';
    print '%option noyywrap';
    print '';
# 
# Candidates for lexical rules are any tokens which represent strings (which
# were part of the bison declarations) and any tokens whose rulenames are
# entirely in uppercase letters (i.e., core rules).  Care should be taken
# with core rules that all strings matching one of the lexical pattern are
# unique (i.e., they really are tokens.  Core rules which are not referenced
# outside of the core rule set need not be unique.
#
    print '%s TOKENST';
    print '';
    printf "%-12s%s\n",'delim',    '[\x3d\x3a\x7b\x7d\x2c\x3b\x2e\x20\x2f\x5b\x5d\x28\x29\x0a\x0d\x09]';
    printf "%-12s%s\n",'nodelim', '[^\x3d\x3a\x7b\x7d\x2c\x3b\x2e\x20\x2f\x5b\x5d\x28\x29\x0a\x0d\x09]';
    my $s;
    foreach $s (@{$self->{rulelist}}) { $s->flexdeclare(); }
    print '';
    print '/* LEXICAL RULES */';
    print '%%';
    print '';
    printf '%-'.($::rulemax+21)."s%s\n",'<TOKENST>{delim}','{ BEGIN(INITIAL); REJECT; }';
    printf '%-'.($::rulemax+21)."s%s\n",'<INITIAL>{nodelim}','{ BEGIN(TOKENST); REJECT; }';
    foreach $s (@{$self->{rulelist}}) { $s->flexrules(); }
    while ($s=pop(@::oline)) { print $s; }
    printf '%-'.($::rulemax+21)."s%s\n",'<*>.','{ return yytext[0]; }';
    print '';
    print '%%';
    print '/* ADDITIONAL C CODE */';
    print '';
}

# =======================================
    package RuleList;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    my $o;
    if ($o = RuleListTerm->new($line)) {
        push @{$self->{terms}}, $o;
        while ($o = RuleListTerm->new($line)) {
            push @{$self->{terms}}, $o;
        }
        $_[0]=$line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $o; foreach $o ( @{$self->{terms}} ) { $o->abnf(); }
}

sub asn1 {
    my $self = shift;
    my $o; foreach $o ( @{$self->{terms}} ) { $o->asn1(); }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $o; foreach $o ( @{$self->{terms}} ) { $o->html(); }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o; foreach $o ( @{$self->{terms}} ) { $o->bisondeclare(); }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o; foreach $o ( @{$self->{terms}} ) {
        $o->bisongrammar();
        while ($o=shift @::intermediates) {
            $o->bisongrammar();
            print '';
            print ';';
            print '';
        }
    }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o; foreach $o ( @{$self->{terms}} ) { $o->flexdeclare(); }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o; foreach $o ( @{$self->{terms}} ) { $o->flexrules(); }
}

# =======================================
    package RuleListTerm;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($self->{rule} = Rule->new($line)) {
        $_[0] = $line;
        return $self;
    }
    elsif ($self->{comm} = Comm->new($line)) {
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $s;
    if    ($s = $self->{rule}) { $s->abnf(); }
    elsif ($s = $self->{comm}) { $s->abnf(); }
}

sub asn1 {
    my $self = shift;
    my $s;
    $::index = -1;
    if    ($s = $self->{rule}) { $s->asn1(); }
    elsif ($s = $self->{comm}) { $s->asn1(); }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $s;
    if    ($s = $self->{rule}) {
        printf '<TR VALIGN=TOP>';
        $s->html();
        print '</TR>';
    }
    elsif ($s = $self->{comm}) { $s->html(); }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $s; if ($s=$self->{rule}) { $s->bisondeclare(); }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $s;
    if    ($s = $self->{rule}) { $s->bisongrammar(); }
    elsif ($s = $self->{comm}) { $s->bisongrammar(); }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $s; if ($s=$self->{rule}) { $s->flexdeclare(); }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $s; if ($s=$self->{rule}) { $s->flexrules(); }
}

# =======================================
    package Comm;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    my $o; while ($o = CWsp->new($line)) { push @{$self->{cwsp}},$o; }
    if ($self->{cnl} = CNl->new($line)) {
        $_[0]=$line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $o; foreach $o ( @{$self->{cwsp}} ) { $o->abnf(); }
    $self->{cnl}->abnf();
}

sub asn1 {
    my $self = shift;
    my $o; foreach $o ( @{$self->{cwsp}} ) { $o->asn1(); }
    $self->{cnl}->asn1();
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $o; foreach $o ( @{$self->{cwsp}} ) { $o->html(); }
    if ($::comments) {
        print '<TR VALIGN=TOP><TD></TD><TD>';
        print '</TD><TD>' if ($::numbers);
        $::nobreak=1;
        $self->{cnl}->html();
        $::nobreak=0;
        print '</TD></TR>';
    }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o; foreach $o ( @{$self->{cwsp}} ) { $o->bisondeclare(); }
    $self->{cnl}->bisondeclare();
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o; foreach $o ( @{$self->{cwsp}} ) { $o->bisongrammar(); }
    $self->{cnl}->bisongrammar();
    print '';
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o; foreach $o ( @{$self->{cwsp}} ) { $o->flexdeclare(); }
    $self->{cnl}->flexdeclare();
}

# =======================================
    package Rule;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($self->{rulename}  = RuleName->new($line) ) {
    if ($self->{definedas} = DefinedAs->new($line)) {
    if ($self->{elements}  = Elements->new($line) ) {
    if ($self->{cnl}       = CNl->new($line)      ) {
        $::defs{$self->{rulename}->{name}}++;
        $::casedefs{lc $self->{rulename}->{name}}++;
        $::tree{lc $self->{rulename}->{name}} = $self->{elements};
        $_[0] = $line;
        return $self;
    } } } }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf "\n\n";
    $self->{rulename}->abnf();
    $self->{definedas}->abnf();
    $::first = 1;
    $self->{elements}->abnf();
    $self->{cnl}->abnf();
}

sub asn1 {
    my $self = shift;
    printf "\n\n";
    $::inrule=0;
    $self->{rulename}->asn1();
    $self->{definedas}->asn1();
    $self->{elements}->asn1();
    $self->{cnl}->asn1();
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    $::ruleno++;
    my $n = $::ruleno;
    printf '<TD ALIGN=RIGHT>'.$n.'.&nbsp;</TD>' if ($::numbers);
    print '<TD>';
    $self->{rulename}->html();
    $self->{definedas}->html();
    print '</TD>';
    print '<TD>';
    $self->{elements}->html();
    $self->{cnl}->html();
    print '</TD>';
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $::flexrule=1;
    $self->{rulename}->bisondeclare();
    $self->{definedas}->bisondeclare();
    $self->{elements}->bisondeclare();
    $self->{cnl}->bisondeclare();
    $self->{flex}=$::flexrule;
    my $name = $self->{rulename}->{name};
    if ($name=~/\U$name\E/) { $self->{flex}=1; } else { $self->{flex}=0; }
    $self->{flex}=0;
    if ($self->{flex}&&$::flexreq{$name}) {
        $name =~ s/-/_/g;
        print '%token TOK_'.$name;
    }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    unless ($self->{flex}) {
        $self->{rulename}->bisongrammar();
        $self->{definedas}->bisongrammar();
        $self->{elements}->bisongrammar();
        printf "\n\t";
        $self->{cnl}->bisongrammar();
        printf "\n;\n\n";
    }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $name = $self->{rulename}->{name};
    if ($name=~/\U$name\E/) { $self->{flex}=1; } else { $self->{flex}=0; }
    $self->{flex}=0;
    if ($self->{flex}) {
        $self->{rulename}->flexdeclare();
        $self->{definedas}->flexdeclare();
        $self->{elements}->flexdeclare();
        $self->{cnl}->flexdeclare();
        print '';
    }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $name = $self->{rulename}->{name};
    if ($self->{flex}&&$::flexreq{$name}) {
        my $oline;
        $oline .= sprintf '%-'.($::rulemax+2).'s    ','{'.$name.'}';
        $oline .= sprintf '{ return TOK_'.$name.'; }';
        push @::oline,$oline;
    } elsif (!$self->{flex}) {
        $self->{rulename}->flexrules();
        $self->{definedas}->flexrules();
        $self->{elements}->flexrules();
        $self->{cnl}->flexrules();
    }
}

# =======================================
    package RuleName;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^([a-z,A-Z][a-z,A-Z,0-9,\-_]*)/) {
        $self->{name} = $1;
        $line = $';
        $::rulename = $self->{name};
        if ($::rulemax<length $::rulename) { $::rulemax=length $::rulename; }
        $_[0] = $line;
        return $self;
    }
    elsif ($line=~/^(<">)/) {
        $self->{name} = $1;
        $line = $';
        $::rulename = $self->{name};
        if ($::rulemax<length $::rulename) { $::rulemax=length $::rulename; }
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf $self->{name};
}

sub asn1 {
    my $self = shift;
    my $name = $self->{name};
    $name=~s/-/_/g;
    printf $name;
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $s = $self->{name};
    printf '<P>';
    printf '<A NAME="'.lc($s).'">';
    if ($::refs{$s}) {
        printf '<A HREF="#Xref.'.$s.'">';
        printf $s;
        printf '</A>';
    } else {
        if ($::ruleno==1 or not $::warnrefs) {
            printf '<FONT COLOR="blue">';
            printf $s;
            printf '</FONT>';
        } elsif ($::caserefs{lc $s} and $::warnings) {
            printf '<A HREF="#OrangeRuleName">';
            printf '<FONT COLOR="orange">';
            printf $s;
            printf '</FONT>';
            printf '</A>';
        } else {
            printf '<A HREF="#RedRuleName">';
            printf '<FONT COLOR="red">';
            printf $s;
            printf '</FONT>';
            printf '</A>';
        }
    }
    printf '</A>';
    $::currentrule = $s;
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $::rule = $self->{name};
    $::rule =~ s/-/_/g;
    $::tindex=0;
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $::rule = $self->{name};
    $::rule =~ s/-/_/g;
    printf $::rule;
    $::iindex=0;
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    printf '%-'.$::rulemax.'s      ',$self->{name};
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $::rule = $self->{name};
    $::rule =~ s/-/_/g;
    $::tindex=0;
}

# =======================================
    package Reference;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^([a-z,A-Z][a-z,A-Z,0-9,\-_]*)/) {
        $self->{name} = $1;
        $line = $';
        $::refs{$self->{name}}++;
        $::caserefs{lc $self->{name}}++;
#       unless ($::rulename=~/\U$::rulename\E/) {
            $::flexreq{$self->{name}}++;
#       }
        $_[0] = $line;
        return $self;
    }
    elsif ($line=~/^(<\">)/) {
        $self->{name} = $1;
        $self->{dquote} = 1;
        $line = $';
        $::refs{$self->{name}}++;
        $::caserefs{lc $self->{name}}++;
#       unless ($::rulename=~/\U$::rulename\E/) {
            $::flexreq{$self->{name}}++;
#       }
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $s = $self->{name};
    if ($s=~/LBRKT/||
        $s=~/LWSP/||
        $s=~/EQUAL/||
        $s=~/COLON/ ) {
        if ($::trace) { printf "\<$::depth\>"; }
        if ($::depth<2&&!$::first) { printf "\n$::indent"; }
    }
    printf $self->{name};
    $::first = 0;
}

sub asn1 {
    my $self = shift;
    my $lname = "\l$self->{name}"; $lname=~s/-/_/g;
    my $uname = "\u$self->{name}"; $uname=~s/-/_/g;
    if ($lname=~/$self->{name}/) {
        printf $uname.' ' unless ($::nextrule||!$::inrule);
        printf $lname;
    } else {
        printf $lname.' ' unless ($::nextrule||!$::inrule);
        printf $uname;
    }
    $::nextrule=0;
#   printf "\l$self->{name} \u$self->{name}";
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $s = $self->{name};
    my $i;
    $i = $::reflist{$s}++;
    $::deflist{$s}[$i] = $::currentrule;
    $i = $::casereflist{lc $s}++;
    $::casedeflist{lc $s}[$i] = $::currentrule;
    if ($::casedefs{lc $s}) {
        printf '<A HREF="#'.lc($s).'">';
        if ($::defs{$s} or not $::warnings) {
            printf $s;
        } else {
            printf '<FONT COLOR="orange">'.$s.'</FONT>';
        }
        printf '</A>';
    } else {
        if ($::warnrefs) {
            printf '<A HREF="#RedReference">';
            printf '<FONT COLOR="red">';
            printf $s;
            printf '</FONT>';
            printf '</A>';
        } else { 
            printf '<FONT COLOR="blue">'.$s.'</FONT>';
        }
    }
    $::first = 0;
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $ref = $self->{name};
    $ref =~ s/-/_/g;
#   if ($ref=~/\U$ref\E/) { $ref='TOK_'.$ref; }
    printf $ref;
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $ref = $self->{name};
#   unless ($ref=~/\U$ref\E/) {
        $::flexrule=0;
#   }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    printf '{'.$self->{name}.'}';
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

# =======================================
    package DefinedAs;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    $self->{wsp1} = NewCWsp->new($line);
    if ($line=~/^\=\//) {
        $self->{incalt} = 1;
        $line = $';
        $self->{wsp2} = NewCWsp->new($line);
        $_[0] = $line;
        return $self;
    }
    elsif ($line=~/^:?\=/) {
        $self->{defini} = 1;
        $line = $';
        $self->{wsp2} = NewCWsp->new($line);
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $o;
    if ($o = $self->{wsp1}) { $o->abnf(); }
    if ($self->{defini}) { printf " =\n\t"; }
    if ($self->{inialt}) { printf " =/\n\t"; }
    if ($o = $self->{wsp2}) { $o->abnf(); }
}

sub asn1 {
    my $self = shift;
    my $o;
    if ($o = $self->{wsp1}) { $o->asn1(); }
    if ($self->{defini}) { printf " ::= "; }
    if ($self->{inialt}) { printf " ::= "; }
    if ($o = $self->{wsp2}) { $o->asn1(); }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->html(); }
    if ($self->{defini}) { printf '<TD VALIGN=TOP>=</TD>'; }
    if ($self->{inialt}) { printf '<TD VALIGN=TOP>=/</TD>'; }
    if ($o = $self->{wsp2}) { $o->html(); }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->bisongrammar(); }
    printf ":\n\t";
    if ($o = $self->{wsp2}) { $o->bisongrammar(); }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->bisondeclare(); }
    if ($o = $self->{wsp2}) { $o->bisondeclare(); }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->flexdeclare(); }
    if ($o = $self->{wsp2}) { $o->flexdeclare(); }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->flexrules(); }
    if ($o = $self->{wsp2}) { $o->flexrules(); }
}

# =======================================
    package Elements;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($self->{alternation} = Alternation->new($line)) {
        $self->{wsp} = NewCWsp->new($line);
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    $self->{alternation}->abnf();
    my $o; if ($o=$self->{wsp}) { $o->abnf(); }
}

sub asn1 {
    my $self = shift;
    $self->{alternation}->asn1();
    my $o; if ($o=$self->{wsp}) { $o->asn1(); }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    $self->{alternation}->html();
    my $o; if ($o=$self->{wsp}) { $o->html(); }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{alternation}->bisongrammar();
    my $o; if ($o=$self->{wsp}) { $o->bisongrammar(); }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{alternation}->bisondeclare();
    my $o; if ($o=$self->{wsp}) { $o->bisondeclare(); }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{alternation}->flexdeclare();
    my $o; if ($o=$self->{wsp}) { $o->flexdeclare(); }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{alternation}->flexrules();
    my $o; if ($o=$self->{wsp}) { $o->flexrules(); }
}

# =======================================
    package CWsp;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    #main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    #if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^[ \t]+/) {
        $line = $';
        $_[0] = $line;
        return $self;
    }
    if ($self->{cnl} = CNl->new($line)) {
        if ($line=~/^[ \t]+/) {
            $line = $';
            $_[0] = $line;
            return $self;
        }
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    if ($self->{cnl}) { $self->{cnl}->abnf(); }
    #print ' ';
}

sub asn1 {
    my $self = shift;
    if ($self->{cnl}) { $self->{cnl}->asn1(); }
    #print ' ';
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    if ($::comments) {
        if ($self->{cnl}) {
            print '<TR VALIGN=TOP><TD></TD><TD>';
            print '</TD><TD>' if ($::numbers);
            $::nobreak=1;
            $self->{cnl}->html();
            $::nobreak=0;
            print '</TD></TR>';
        }
    }
    #print ' ';
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if ($self->{cnl}) { $self->{cnl}->bisongrammar(); }
    printf ' ';
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

# =======================================
    package NewCWsp;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    #main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    #if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^((;([^\n]*))?\n)?[ \t]+/) {
        if ($3) { push @{$self->{comments}}, $3; }
        $line=$';
        while ($line=~/^((;([^\n]*))?\n)?[ \t]+/) {
            if ($3) { push @{$self->{comments}}, $3; }
            $line=$';
        }
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $o; foreach $o ( @{$self->{comments}} ) { printf "\t;".$o."\n\t"; }
}

sub asn1 {
    my $self = shift;
    my $o; foreach $o ( @{$self->{comments}} ) { printf "\t--".$o."\n\t"; }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    if ($::comments) {
        my $o; foreach $o ( @{$self->{comments}} ) {
            printf '&nbsp;&nbsp;<FONT COLOR="magenta">;'.$o.'</FONT>';
            printf "\n<BR>" unless ($::nobreak);
        }
    }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o; foreach $o ( @{$self->{comments}} ) {
        printf '/* '.$o.' */';
    }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

# =======================================
    package CNl;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^\n/) {
        $line=$';
        $_[0]=$line;
        return $self;
    } elsif ($self->{comment}=Comment->new($line)) {
        $_[0]=$line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $s; if ($s = $self->{comment}) { $s->abnf() }
}

sub asn1 {
    my $self = shift;
    my $s; if ($s = $self->{comment}) { $s->asn1() }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $s; if ($s = $self->{comment}) { $s->html() }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $s; if ($s = $self->{comment}) { $s->bisongrammar() }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

# =======================================
    package Comment;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^;([^\n]*)/) {
        $self->{comment}=$1;
        $line=$';
        if ($line=~/^\n/) {
            $line=$';
            $_[0] = $line;
            return $self;
        }
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf "\t;".$self->{comment};
}

sub asn1 {
    my $self = shift;
    printf "\t--".$self->{comment};
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    if ($::comments) {
        printf '&nbsp;&nbsp;<FONT COLOR="magenta">;'.$self->{comment}.'</FONT>';
        printf "\n<BR>" unless ($::nobreak);
    }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    printf '/* '.$self->{comment}.' */';
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

# =======================================
    package Alternation;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($self->{cont} = Concatenation->new($line)) {
        my $o;
        while ($o = AltTerm->new($line)) {
            push @{$self->{terms}}, $o;
        }
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    $::depth++;
    $self->{cont}->abnf();
    my $s; foreach $s ( @{$self->{terms}} ) { $s->abnf(); }
    $::depth--;
}

sub asn1 {
    my $self = shift;
    my $s;
    my $i = $::inrule;
    if ($self->{terms}) {
        $::indent .= "\t";
        $::index++;
        if ($::inrule&&!$::nextrule) { printf "choice "; }
        if ($::nextrule) { $::nextrule=0; }
        printf "CHOICE {";
        printf "\n$::indent";
        $::inrule=1;
        $self->{cont}->asn1();
        foreach $s (@{$self->{terms}}) { $::index++; $s->asn1(); }
        $::indent =~ s/.//;
        $::inrule=$i;
        printf "\n$::indent}";
    } else {
        $self->{cont}->asn1();
    }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    $::depth++;
    $self->{cont}->html();
    my $s; foreach $s ( @{$self->{terms}} ) { $s->html(); }
    $::depth--;
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{cont}->bisongrammar();
    my $s; foreach $s ( @{$self->{terms}} ) { $s->bisongrammar(); }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{cont}->bisondeclare();
    my $s; foreach $s ( @{$self->{terms}} ) { $s->bisondeclare(); }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if ($self->{terms}) {
        # printf '(';
        $self->{cont}->flexdeclare();
        my $s; foreach $s ( @{$self->{terms}} ) { $s->flexdeclare(); }
        # printf ')';
    } else {
        $self->{cont}->flexdeclare();
    }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{cont}->flexrules();
    my $s; foreach $s ( @{$self->{terms}} ) { $s->flexrules(); }
}

# =======================================
    package AltTerm;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($self->{wsp1} = NewCWsp->new($line)) {
        if ($line=~/^([\/\|])/) {
            $self->{symbol}=$1;
            $line = $';
            $self->{wsp2} = NewCWsp->new($line);
            if ($self->{conc} = Concatenation->new($line)) {
                $_[0] = $line;
                return $self;
            }
        }
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    $self->{wsp1}->abnf();
    printf " $self->{symbol}";
    if ($::depth<4) {
        #if ( (not $self->{wsp2} || not $self->{wsp2}->{comments} ) && not @{$self->{wsp1}->{comments}} ) {
        if ( not @{$self->{wsp1}->{comments}} ) {
            printf "\n$::indent";
            $::first = 1;
        } else {
            printf ' ';
            $::first = 0;
        }
    } else {
        printf ' ';
        $::first = 0;
    }
    my $o; if ($o = $self->{wsp2}) { $o->abnf(); }
    my $np = $::noparen;
    $::noparen=1;
    $self->{conc}->abnf();
    $::noparen=$np;
}

sub asn1 {
    my $self = shift;
    $self->{wsp1}->asn1();
    printf ",\n$::indent";
    my $o; if ($o = $self->{wsp2}) { $o->asn1(); }
    $self->{conc}->asn1();
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    $self->{wsp1}->html();
    printf " $self->{symbol} ";
    my $o; if ($o = $self->{wsp2}) { $o->html(); }
    $self->{conc}->html();
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{wsp1}->bisongrammar();
    printf "\n\t".'| ';
    my $o; if ($o = $self->{wsp2}) { $o->bisongrammar(); }
    $self->{conc}->bisongrammar();
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{wsp1}->bisondeclare();
    my $o; if ($o = $self->{wsp2}) { $o->bisondeclare(); }
    $self->{conc}->bisondeclare();
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{wsp1}->flexdeclare();
    printf '|';
    my $o; if ($o = $self->{wsp2}) { $o->flexdeclare(); }
    $self->{conc}->flexdeclare();
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{wsp1}->flexrules();
    my $o; if ($o = $self->{wsp2}) { $o->flexrules(); }
    $self->{conc}->flexrules();
}

# =======================================
    package Concatenation;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($self->{repetition}=Repetition->new($line)) {
        my $o;
        while ($o = ConcTerm->new($line)) {
            push @{$self->{terms}}, $o;
        }
        $_[0]=$line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    $self->{repetition}->abnf();
    my $s; foreach $s (@{$self->{terms}}) { $s->abnf(); }
}

sub asn1 {
    my $self = shift;
    my $s;
    my $i = $::inrule;
    if ($self->{terms}) {
        $::indent .= "\t";
        my $index = $::index;
        $::index = 0;
        if ($::inrule&&!$::nextrule) { printf "sequence "; }
        if ($::nextrule) { $::nextrule=0; }
        printf "SEQUENCE {";
        printf "\n$::indent";
        $::inrule=1;
        $self->{repetition}->asn1();
        foreach $s (@{$self->{terms}}) { $::index++; $s->asn1(); }
        $::indent =~ s/.//;
        printf "\n$::indent}";
        $::inrule = $i;
        $::index = $index;
    } else {
        $self->{repetition}->asn1();
    }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    $self->{repetition}->html();
    my $s; foreach $s (@{$self->{terms}}) { $s->html(); }
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{repetition}->bisongrammar();
    my $s; foreach $s (@{$self->{terms}}) { $s->bisongrammar(); }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{repetition}->bisondeclare();
    my $s; foreach $s (@{$self->{terms}}) { $s->bisondeclare(); }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{repetition}->flexdeclare();
    my $s; foreach $s (@{$self->{terms}}) { $s->flexdeclare(); }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{repetition}->flexrules();
    my $s; foreach $s (@{$self->{terms}}) { $s->flexrules(); }
}

# =======================================
    package ConcTerm;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($self->{wsp} = NewCWsp->new($line)) {
        if ($self->{repetition}=Repetition->new($line)) {
            $_[0] = $line;
            return $self;
        }
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf ' ';
    if ($self->{wsp}) { $self->{wsp}->abnf(); }
    $self->{repetition}->abnf();
}

sub asn1 {
    my $self = shift;
    printf ",\n$::indent";
    $self->{wsp}->asn1();
    $self->{repetition}->asn1();
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    printf ' ';
    $self->{wsp}->html();
    $self->{repetition}->html();
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    printf ' ';
    $self->{wsp}->bisongrammar();
    $self->{repetition}->bisongrammar();
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{wsp}->bisondeclare();
    $self->{repetition}->bisondeclare();
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{wsp}->flexdeclare();
    $self->{repetition}->flexdeclare();
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{wsp}->flexrules();
    $self->{repetition}->flexrules();
}

# =======================================
    package Repetition;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    $self->{repeat}=Repeat->new($line);
    $self->{wsp} = NewCWsp->new($line);
    if ($self->{element}=Element->new($line)) {
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $np = $::noparen;
    $::noparen=0;
    if ($self->{repeat}) { $self->{repeat}->abnf(); }
    else { $::noparen=1; }
    $self->{element}->abnf();
    $::noparen=$np;
}

sub asn1 {
    my $self = shift;
    if ($self->{repeat}) { $self->{repeat}->asn1(); }
    $self->{element}->asn1();
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    if ($self->{repeat}) { $self->{repeat}->html(); }
    $self->{element}->html();
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if ($self->{repeat}) {
        my $s; if ($s=$self->{intermediate}) { printf $s->{name}; return; }
        my $rule = '_'.$::rule.$::iindex++;
        printf $rule;
        $self->{intermediate}=Intermediate->new($rule,$self);
    } else {
        $self->{element}->bisongrammar();
    }
}

sub bisonexpand {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $rule = shift;
    if (defined $self->{repeat}->{rep}) {
        if ($::verbose) { printf '/* simple repeat */'; }
        my $i;
        for ($i=0;$i<$self->{repeat}->{rep};$i++) {
            $self->{element}->bisongrammar();
            printf ' ';
        }
    } elsif (defined $self->{repeat}->{beg}) {
        if ($self->{repeat}->{beg}>0) {
            if ($::verbose) { printf '/* minimum repeat */'; }
            my $i;
            for ($i=0;$i<$self->{repeat}->{beg};$i++) {
                $self->{element}->bisongrammar();
                printf ' ';
            }
            printf "\n\t".'| ';
            printf $rule;
            printf ' ';
            $self->{element}->bisongrammar();
        } else {
            if ($::verbose) { printf '/* unlimited repeat */'; }
            printf '/* empty */'."\n\t".'| ';
            $self->{element}->bisongrammar();
            printf "\n\t".'| ';
            printf $rule;
            printf ' ';
            $self->{element}->bisongrammar();
        }
    }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{element}->bisondeclare();
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{element}->flexdeclare();
    if ($self->{repeat}&&defined $self->{repeat}->{rep}) {
        if ($::verbose) { printf '/* simple repeat */'; }
        printf '{'.$self->{repeat}->{rep}.'}';
    } elsif ($self->{repeat}&&defined $self->{repeat}->{beg}) {
        if ($self->{repeat}->{beg}||$self->{repeat}->{end}) {
            if ($::verbose) { printf '/* limited repeat */'; }
            if ($self->{repeat}->{beg}==1&&!$self->{repeat}->{end}) {
                printf '+';
            } else {
                printf '{'.$self->{repeat}->{beg}.','.$self->{repeat}->{end}.'}';
            }
        } else {
            if ($::verbose) { printf '/* unlimited repeat */'; }
            printf '*';
        }
    }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{element}->flexrules();
}

# =======================================
    package Repeat;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^([0-9]*[#*][0-9]*)/) {
        $self->{repeat}=$1;
        $line = $';
        $self->{repeat} =~ /^([0-9]*)[#*]([0-9]*)/;
        $self->{beg}=$1;
        $self->{end}=$2;
        $_[0]=$line;
        return $self;
    }
    if ($line=~/^([0-9][0-9]*)/) {
        $self->{repeat}=$1;
        $line = $';
        $self->{rep}=$1;
        $_[0]=$line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf $self->{repeat};
}

sub asn1 {
    my $self = shift;
    my $p;
    my $i = $::inrule;
#   $p = 'SEQUENCE OF (SIZE('.$self->{repeat}.')) ';
    $p = 'SEQUENCE OF ';
    $p =~ s/[*]/../;
    $p =~ s/\[1\.\.\]/\[\+\]/;
    $p =~ s/\[\.\.\]/\[\*\]/;
    if ($i) { printf "array "; }
    $::nextrule=1;
    printf $p;
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    printf $self->{repeat};
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

# =======================================
    package Element;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($self->{element} = Reference->new($line)) {
        $_[0] = $line;
        return $self;
    } elsif ($self->{element} = Group->new($line)) {
        $_[0] = $line;
        return $self;
    } elsif ($self->{element} = Option->new($line)) {
        $_[0] = $line;
        return $self;
    } elsif ($self->{element} = CharVal->new($line)) {
        $_[0] = $line;
        return $self;
    } elsif ($self->{element} = NumVal->new($line)) {
        $_[0] = $line;
        return $self;
    } elsif ($self->{element} = ProseVal->new($line)) {
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    $self->{element}->abnf();
}

sub asn1 {
    my $self = shift;
    $self->{element}->asn1();
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    $self->{element}->html();
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{element}->bisongrammar();
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{element}->bisondeclare();
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{element}->flexdeclare();
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{element}->flexrules();
}

# =======================================
    package Group;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^\(/) {
        $line = $';
        $self->{wsp1} = NewCWsp->new($line);
        if ($self->{alternation}=Alternation->new($line)) {
            $self->{wsp2} = NewCWsp->new($line);
            if ($line=~/^\)/) {
                $line = $';
                $_[0] = $line;
                return $self;
            }
        }
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $o;
    printf '( ' unless ($::noparen);
    if ($o = $self->{wsp1}) { $o->abnf(); }
    $self->{alternation}->abnf();
    if ($o = $self->{wsp2}) { $o->abnf(); }
    printf ' )' unless ($::noparen);
}

sub asn1 {
    my $self = shift;
    my $o;
    if ($o = $self->{wsp1}) { $o->asn1(); }
    $self->{alternation}->asn1();
    if ($o = $self->{wsp2}) { $o->asn1(); }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $o;
    printf '( ';
    if ($o = $self->{wsp1}) { $o->html(); }
    $self->{alternation}->html();
    if ($o = $self->{wsp2}) { $o->html(); }
    printf ' )';
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $s; if ($s=$self->{intermediate}) { printf $s->{name}; return; }
    my $rule = '_'.$::rule.$::iindex++;
    printf $rule;
    $self->{intermediate}=Intermediate->new($rule,$self);
}

sub bisonexpand {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $rule = shift;
    my $o;
    if ($o = $self->{wsp1}) { $o->bisongrammar(); }
    $self->{alternation}->bisongrammar();
    if ($o = $self->{wsp2}) { $o->bisongrammar(); }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->bisondeclare(); }
    $self->{alternation}->bisondeclare();
    if ($o = $self->{wsp2}) { $o->bisondeclare(); }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    printf '(';
    if ($o = $self->{wsp1}) { $o->flexdeclare(); }
    $self->{alternation}->flexdeclare();
    if ($o = $self->{wsp2}) { $o->flexdeclare(); }
    printf ')';
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->flexrules(); }
    $self->{alternation}->flexrules();
    if ($o = $self->{wsp2}) { $o->flexrules(); }
}

# =======================================
    package Option;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^\[/) {
        $line = $';
        $self->{wsp1} = NewCWsp->new($line);
        if ($self->{alternation}=Alternation->new($line)) {
            $self->{wsp2} = NewCWsp->new($line);
            if ($line=~/^\]/) {
                $line = $';
                $_[0] = $line;
                return $self;
            }
        }
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    my $o;
    printf '[';
    my $np = $::noparen;
    $::noparen=1;
    if ($o = $self->{wsp1}) { $o->abnf(); }
    $self->{alternation}->abnf();
    if ($o = $self->{wsp2}) { $o->abnf(); }
    $::noparen=$np;
    printf ']';
}

sub asn1 {
    my $self = shift;
    my $o;
    if ($o = $self->{wsp1}) { $o->asn1(); }
    $self->{alternation}->asn1();
    printf " OPTIONAL ";
    if ($o = $self->{wsp2}) { $o->asn1(); }
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    my $o;
    printf '[';
    if ($o = $self->{wsp1}) { $o->html(); }
    $self->{alternation}->html();
    if ($o = $self->{wsp2}) { $o->html(); }
    printf ']';
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $s; if ($s=$self->{intermediate}) { printf $s->{name}; return; }
    my $rule = '_'.$::rule.$::iindex++;
    printf $rule;
    $self->{intermediate}=Intermediate->new($rule,$self);
}

sub bisonexpand {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $rule = shift;
    printf '/* empty */'."\n\t".'| ';
    my $o;
    if ($o = $self->{wsp1}) { $o->bisongrammar(); }
    $self->{alternation}->bisongrammar();
    if ($o = $self->{wsp2}) { $o->bisongrammar(); }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->bisondeclare(); }
    $self->{alternation}->bisondeclare();
    if ($o = $self->{wsp2}) { $o->bisondeclare(); }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    printf '(';
    if ($o = $self->{wsp1}) { $o->flexdeclare(); }
    $self->{alternation}->flexdeclare();
    if ($o = $self->{wsp2}) { $o->flexdeclare(); }
    printf ')?';
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $o;
    if ($o = $self->{wsp1}) { $o->flexrules(); }
    $self->{alternation}->flexrules();
    if ($o = $self->{wsp2}) { $o->flexrules(); }
}

# =======================================
    package CharVal;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^"([^"]*)"/) {
        $self->{charval}=$1;
        $line = $';
        if ($::rulemax<length $self->{charval}) { $::rulemax=length $self->{charval}; }
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
#   if (length $self->{charval}<2) {
#       printf "%s%2x",'%x',ord($self->{charval});
#   } else {
        printf '"'.$self->{charval}.'"';
#   }
}

sub asn1 {
    my $self = shift;
    printf 'dummy ' unless ($::nextrule||!$::inrule);
    $::nextrule=0 if ($::nextrule);
    printf 'NULL_PARM("'.$self->{charval}.'")';
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    printf '"<FONT COLOR="green">'.$self->{charval}.'</FONT>"';
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if ($self->{token}) {
        printf $self->{token};
    } else {
        printf "'".$self->{charval}."'";
    }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if (length $self->{charval}>1) {
        $self->{token} = 'TOK_'."\U$::rule\E".$::tindex++;
        print '%token '.$self->{token}.' "'.$self->{charval}.'"';
    }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if (length $self->{charval}>1) {
        printf main->escape($self->{charval});
    } else {
        printf '\%03o',ord($self->{charval});
    }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if (length $self->{charval}>1) {
        my $rule = main->escape($self->{charval});
        my $name = "\U$::rule\E".$::tindex++;
        my $oline;
        $oline .= sprintf '<INITIAL>%-'.($::rulemax+10).'s  ', $rule.'/{delim}';
        $oline .= sprintf '{ return TOK_'.$name.'; }';
        push @::oline,$oline;
    }
}

# =======================================
    package NumVal;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^%/) {
        $line = $';
        if ($self->{numval}=BinVal->new($line)) {
            $_[0] = $line;
            return $self;
        } elsif ($self->{numval}=DecVal->new($line)) {
            $_[0] = $line;
            return $self;
        } elsif ($self->{numval}=HexVal->new($line)) {
            $_[0] = $line;
            return $self;
        }
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf '%';
    $self->{numval}->abnf();
}

sub asn1 {
    my $self = shift;
    printf 'dummy ' unless ($::nextrule||!$::inrule);
    $::nextrule=0;
    printf 'NULL_PARM(';
    $self->{numval}->asn1();
    printf ')';
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    printf '%';
    $self->{numval}->html();
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{numval}->bisongrammar();
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{numval}->bisondeclare();
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{numval}->flexdeclare();
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
#   $self->{numval}->flexrules();
}

# =======================================
    package BinVal;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^b([01]+((.[01]+)+|(-[01]+))?)/) {
        $self->{num}=$1;
        $line=$';
        $_[0]=$line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf 'b'.$self->{num};
}

sub asn1 {
    my $self = shift;
    printf '0b'.$self->{num};
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    printf 'b'.$self->{num};
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if ($self->{token}) {
        printf $self->{token};
    } else {
        printf '0b'.$self->{num}.' /* no token! */';
    }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{token}='TOK_'."\U$::rule\E".$::tindex++;
    print '%token '.$self->{token}.' 0b'.$self->{num};
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    printf '\b'.$self->{num};
}

# =======================================
    package DecVal;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^d([0-9]+((.[0-9]+)+|(-[0-9]+))?)/) {
        $self->{num}=$1;
        $line=$';
        $_[0]=$line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf 'd'.$self->{num};
}

sub asn1 {
    my $self = shift;
    printf $self->{num};
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    printf 'd'.$self->{num};
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    if ($self->{token}) {
        printf $self->{token};
    } else {
        printf $self->{num}.' /* no token! */';
    }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    $self->{token}='TOK_'."\U$::rule\E".$::tindex++;
    print '%token '.$self->{token}.' '.$self->{num};
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    printf '\%03o',$self->{num};
}

# =======================================
    package HexVal;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^x([0-9,A-F,a-f]+((\.[0-9,A-F,a-f]+)+|(-[0-9,A-F,a-f]+))?)/) {
        $self->{num}="\U$1";
        $line=$';
        $self->{num} =~ /([0-9,A-F,a-f]+)[-]?([0-9,A-F,a-f]+)?/;
        $self->{beg}="\U$1";
        $self->{end}="\U$2";
        $_[0]=$line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf 'x'.$self->{num};
}

sub asn1 {
    my $self = shift;
    printf '0x'.$self->{num};
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    printf 'x'.$self->{num};
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $i;
    if ($self->{end}) {
        for ($i=hex $self->{beg};$i<=hex $self->{end};$i++) {
            unless ($i==hex $self->{beg}) { printf "\n\t".'| '; }
            printf "'";
            if ($i>31&&$i<127&&$i!=39&&$i!=92) { printf "%c",$i; } else { printf '\%03o',$i; }
            printf "'";
        }
    } else {
        $i=hex $self->{beg};
        printf "'";
        if ($i>31&&$i<127&&$i!=39&&$i!=92) { printf "%c",$i; } else { printf '\%03o',$i; }
        printf "'";
    }
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    my $i;
    if ($self->{end}) {
        printf '[';
        printf '\x'.lc($self->{beg});
#       $i=hex $self->{beg};
#       if ($i>31&&$i<127&&$i!=39&&$i!=92) {
#           printf main->escape(chr($i)); } else { printf '\%03o',$i; }
        printf '-';
        printf '\x'.lc($self->{end});
#       $i=hex $self->{end};
#       if ($i>31&&$i<127&&$i!=39&&$i!=92) {
#           printf main->escape(chr($i)); } else { printf '\%03o',$i; }
        printf ']';
    } else {
        printf '\x'.lc($self->{beg});
#       $i=hex $self->{beg};
#       if ($i>31&&$i<127&&$i!=39&&$i!=92) {
#           printf main->escape(chr($i)); } else { printf '\%03o',$i; }
    }
}

# =======================================
    package ProseVal;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    main->getone($_[0],$type);
    $::depth++;
    my $ret = $self->read(@_);
    if ($ret) { main->gotone($_[0],$type); }
    $::depth--;
    return $ret;
}

sub read {
    my $self = shift;
    my $line = $_[0];
    if ($line=~/^<([^>]*)>/) {
        $self->{val}=$1;
        $line = $';
        if ($self->{val}=~/defined in \[(\w+)\]/) { $self->{xref} = lc($1.'.html').'#'.$::rulename; }
        $_[0] = $line;
        return $self;
    }
    unless ($::error && $::errdep > $::depth ) { $::error = $line; $::errdep = $::depth; }
    return 0;
}

sub abnf {
    my $self = shift;
    printf '<'.$self->{val}.'>';
}

sub asn1 {
    my $self = shift;
    printf '<'.$self->{val}.'>';
}

sub html {
    my $self = shift;
    if ($::trace) { printf '&lt;'.ref($self).'&gt;'; }
    printf '&lt;<FONT COLOR="magenta">';
    if ($self->{xref}) { printf '<A HREF='.lc($self->{xref}).'>'; }
    printf $self->{val};
    if ($self->{xref}) { printf '</A>'; }
    printf '</FONT>&gt;';
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    printf '/* '.$self->{val}.' */';
}

sub bisondeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexdeclare {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

sub flexrules {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
}

# =======================================
    package Intermediate;
    use strict;
# =======================================

sub new {
    my $type = shift;
    my $self = {};
    bless $self, $type;
    $self->{name}=shift;
    $self->{root}=shift;
    push @::intermediates,$self;
    return $self;
}

sub bisongrammar {
    my $self = shift;
    if ($::verbose) { printf '/* '.ref($self).' */'; }
    printf $self->{name}.':'."\n\t";
    $self->{root}->bisonexpand($self->{name});
}

# =======================================
    package main;
    use strict;
# =======================================

sub getline {
    my $type = shift;
    my $line = $_[0];
    my $inline = '';
    until ($line=~/[^\n]$/) {
        $::lineno++;
        $inline = <$::ifh>;
        unless ($inline) { $::done = 1; return 1; }
        chomp $inline;
        if ($::lineno != 1) { $inline = "\n".$inline; }
        $line = $line.$inline;
        $::next = $::next.$inline;
    }
    $_[0] = $line;
    return 0;
}

sub getlines {
    my $type = shift;
    my $line = $_[0];
    my $inline = '';
    until ($line=~/\n\n/) {
        $::lineno++;
        $inline = <$::ifh>;
        unless ($inline) {
            $::done = 1;
            $_[0] = $line;
            return;
        }
        $line = $line.$inline;
    }
    $_[0] = $line;
}

sub getone {
    my $type = shift;
    my $line = $_[0];
    my $obj = $_[1];
    my $i;
    if ($::debug) {
        for ($i=0;$i<$::depth;$i++) { printf " "; }
        printf "\<".$obj."\>\n";
        for ($i=0;$i<$::depth;$i++) { printf " "; }
        $line =~ /([^\n]*)/;
        printf "\`$1\'\n";
    }
}

sub gotone {
    my $type = shift;
    my $line = $_[0];
    my $obj = $_[1];
    my $i;
    if ($::debug) {
        for ($i=0;$i<$::depth;$i++) { printf " "; }
        printf "\<".$obj."\> \<--Got\n";
        for ($i=0;$i<$::depth;$i++) { printf " "; }
        $line =~ /([^\n]*)/;
        printf "\`$1\'\n";
    }
}

sub escape {
    my $type = shift;
    my $chars = shift;
    $chars =~ s/\\/\\\\/g;
    $chars =~ s/\[/\\\[/g;
    $chars =~ s/\]/\\\]/g;
    $chars =~ s/\{/\\\{/g;
    $chars =~ s/\}/\\\}/g;
    $chars =~ s/\(/\\\(/g;
    $chars =~ s/\)/\\\)/g;
    $chars =~ s/\*/\\\*/g;
    $chars =~ s/\+/\\\+/g;
    $chars =~ s/\?/\\\?/g;
    $chars =~ s/\|/\\\|/g;
    $chars =~ s/\./\\\./g;
    $chars =~ s/\$/\\\$/g;
    $chars =~ s/\^/\\\^/g;
    $chars =~ s/\-/\\\-/g;
    $chars =~ s/"/\\"/g;
    $chars =~ s/ /\\x20/g;
    return $chars;
}

no strict;

$line = '';
$lineno = 0;
$done = 0;
$error = '';
$errdep = 0;
$indent = "\t";
$index = 0;
$prefix = 0;
$depth = 0;
$first = 0;
$inrule = 0;

if ($abnf = Abnf->new($line)) {
    if ($gasn  ) { $abnf->asn1();  }
    if ($gabnf ) { $abnf->abnf();  }
    if ($ghtml ) { $abnf->html();  }
    if ($gbison) { $abnf->bison(); }
    if ($gflex ) { $abnf->flex();  }
} else {
    print "PARSE FAILED!";
}

