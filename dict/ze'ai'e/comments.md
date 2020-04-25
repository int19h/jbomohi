## 2018-06-04T17:39:35Z — gleki (comment 3373, on definition 68931)

{setese te se} is just {te}



## 2020-04-25T20:37:26Z — krtisfranks (comment 3546)

Zooming format

There are two formats for things like addresses, human names, etc.

(1) One format starts at a large (but possibly arbitrary scale) and then
zooms in to the smallest relevant scale or member. If there is an ordering
'<' on the set (usually a form of containment or membership so that the
term on the right-hand side is bigger than the term on the left-hand
side), then the string "x1 x2 x3 ... x_(n-1) x_n" implies that x_n <
x_(n-1) < ... < x3 x2 < x1.
For house addresses, this would be like starting with the country, then
specifying the administrative sub-unit, then the local community or
metropolitan area, then the city or town, then then district or ward
thereof, then the street, then the building number/name, and then the
door/apartment label.
Computer directory architecture works this way (moving forward in the file
location specifies a path through subtrees).
Chinese names work this way too: the first name specifies the family, then
subsequent names specify subdivisions thereof until the
specific/individual/personal name is reached.
In taxonomy, this would be going in the order 'domain, kingdom, phylum,
class, order, family, genus, species, subspecies' (or something similar.

(2) Another format is the exact opposite. It starts specific and goes
general. "x1 x2 x3 ... x_(n-1) x_n" indicates that x1 < x2 < x3 < ... <
x_(n-1) < x_n.
U.S. house addresses generally work this way. First is the building and
door label (admittedly, understood as a single group but specified in that
order), then the steet, then the city or town, then the county, then the
state, then the country (with ZIP code breaking the pattern by going at
the end).
English names also follow this pattern (ignoring middle names and
ordinals): the first name is the personal/specific name and the last name
is the family name.

Lojban generally seems to adopt strategy (2) because having arbitrarily
many sumti for a given order-relation selbri is only practicable if the
arbitrary slots begin at the end. If they occurred at the beginning, then
figuring out whether the nth sumti (for n > 1) belongs to this ordering
relation or is just acting in an entirely different role in the predicate
is difficult without additional features in the language or convention.
Even context cannot be used because that would make syntactic parsing
ambiguous.

However, (1) is a more logical way to operate in many ways, and the choice
to go exclusively with (2) in a sense breaks cultural neutrality.

Thus, this word can be used in order to reverse the specification format
from (2) to (1) or vice-versa, if the only sumti which ever are mentioned
for the given selbri belong only to the ordering terms of the terbri
thereof (in other words: are the arbitrary terms).

