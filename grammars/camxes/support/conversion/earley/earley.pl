#!/usr/bin/perl

use Data::Dumper;
use strict;

my(%grammar);

my $verbose = 0;
if($ARGV[0] eq '-v') { shift @ARGV; $verbose = 1; }

%grammar = %{ require $ARGV[0] };

undef $/;
my $input = <STDIN>;
$input =~ s/^\s+//g;
$input =~ s/\s+$//g;
my @sentence = split/\s+/,$input;

# $grammar{'LHSname'}->[$RHSaryidx]->[$RHStokenidx]
# @chart = ( $chartref0, $chartref1, $chartrefn );
# $chartrefn = [ 'LHSname', $RHSaryidx, $afterdotidx, $pos, $chartid ]

my @chart;

print "initial " if $verbose;
&enqueue([ $ARGV[1], 0, 0, 0, 0 ], 0);

for(my $i=0; $i<=@sentence; $i++) {
  print "*** chart $i\n" if $verbose;
  my $startsize;
  do {
      $startsize = $#{ $chart[$i] };
      for(my $j=0; $j<=$#{ $chart[$i] }; $j++) {
	  my $state = $chart[$i]->[$j];
	  if(&incomplete($state)) {
	      if(&nextisnonterminal($state)) {
		  &predict($state);
	      } else {
		  &scan($state);
	      }
	  } else {
	      &complete($state);
	  }
      }
  } while($startsize!=$#{ $chart[$i] });
}

my $completeparses = 0;
foreach my $state (@{ $chart[@sentence] }) {
  if(($state->[0] eq $ARGV[1]) &&
     ($state->[2] == scalar @{ $grammar{$ARGV[1]}->[$state->[1]] }) &&
     ($state->[3] == 0) &&
     ($state->[4] == scalar @sentence)) {
    $completeparses++;
  }
}

if($completeparses) {
  print "valid sentence\n";
  exit 0;
} else {
  print "invalid sentence\n";
  exit 1;
}

sub nextisnonterminal {
  my $state = shift;
  my $B = $grammar{$state->[0]}->[$state->[1]]->[$state->[2]];
  return defined($grammar{$B});
}

sub incomplete {
  my $state = shift;
  my @RHS = @{ $grammar{$state->[0]}->[$state->[1]] };
  return ($state->[2] != scalar @RHS);
}

sub enqueue {
  my $state = shift;
  printf("enqueueing: %s\n",prettystate($state)) if $verbose;
  my $chartidx = shift;
  foreach my $iterstate (@{ $chart[$chartidx] }) {
    my $matchcnt = 0;
    map { if($state->[$_] eq $iterstate->[$_]) { $matchcnt++; } } (0..4);
    if($matchcnt==5) { return; }
  }
  push @{ $chart[$chartidx] }, $state;
}

sub predict {
  my $state = shift;
  printf("predicter: %s\n", prettystate($state)) if $verbose;
  my $B = $grammar{$state->[0]}->[$state->[1]]->[$state->[2]];
  for(my $RHSaryidx=0; $RHSaryidx<=$#{$grammar{$B}}; $RHSaryidx++) {
    my $newstate = [ $B, $RHSaryidx, 0, $state->[4], $state->[4] ];
    print "predicter " if $verbose;
    enqueue($newstate, $state->[4]);
  }
}

sub scan {
  my $state = shift;
  printf("scanner:   %s\n", prettystate($state)) if $verbose;
  my $B = $grammar{$state->[0]}->[$state->[1]]->[$state->[2]];
  if($B eq $sentence[$state->[4]]) {
    my $newstate = [ $state->[0], $state->[1], $state->[2]+1, $state->[3], $state->[4] + 1 ];
    print "scanner " if $verbose;
    enqueue($newstate, $state->[4] + 1);
  }
}

sub complete {
  my $state = shift;
  printf("completer: %s\n", prettystate($state)) if $verbose;
  for(my $j=0; $j<=$state->[3]; $j++) {
    foreach my $iterstate (@{ $chart[ $j ] }) {
      my $iterB = $grammar{$iterstate->[0]}->[$iterstate->[1]]->[$iterstate->[2]];
      if(($iterB eq $state->[0]) and ($iterstate->[4]==$state->[3])){
	my $newstate = [ $iterstate->[0], $iterstate->[1], $iterstate->[2]+1, $iterstate->[3], $state->[4] ];
	print "completer " if $verbose;
	enqueue($newstate, $state->[4]);
      }
    }
  }
}

sub prettystate {
  my $state = shift;
  my @rhs = @{ $grammar{$state->[0]}->[$state->[1]] };
  splice @rhs, $state->[2], 0, ".";
  return sprintf("%s -> %s [%i,%i]", $state->[0], join(" ",@rhs), $state->[3], $state->[4]);
}
