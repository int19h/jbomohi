## 2019-04-24T18:46:59Z — krtisfranks (comment 3478, on definition 66354)

Clarification

This definition says that it "attaches "{te'ai} {ni'u} {pa}" to all
subsequent unit-selbri in the tanru" (or is essentially equivalent to
doing so). We should reinforce that this means that we do not have the
"per second per second" issue which arises in English. For example, in
English, "meters per second per second" means m*(s^(-2)) = m/(s^(-2)).
(This is even though it could conceivably be construed to be equivalent to
just m). In Lojban, the former meaning would simply be "{mitre} fei'u
{snidu} te'ai {re}" or "mitre fei'u snidu ({bo}?) {pi'ai} snidu"; the
latter, on the other hand, would be given by "mitre fei'u snidu fei'u
snidu" (see below).

Nesting should probably also be explicitly handled. (The obvious meaning
is that it reciprocates, which is an involution). In other words, count
how many "fei'u"s precede the given unit in the relevant construct; if the
number is even, then the unit is in the numerator; if the number is odd,
then that unit is in the denominator.


The scope should be elaborated too. I personally think that it should
group everything previous to it as a unit until it hits (from the right to
left) the first number coefficient (units-mantissa), mekso operator, or
something like "{li}", "{lo}", or "{cu}"; so, "{ki'otre} tei'a re fei'u"
means "square kilometers per […]" rather than "km^(2/[…])", which is
pragmatically absurd and a utility which can be gained by the usage of
other words; meanwhile, it should continue until the end of the
units-string - in particular, "pi'ai" and "te'ai" have higher priority
than this word; so, "mitre fei'u snidu bo pi'ai snidu" is the same as
"mitre fei'u snidu pi'ai snidu", and both would mean 'm/(s^2)'; the issue
is that it would need a terminator (although any mekso operator without
"bo" would work just as well).


Oh, and these words essentially make units (whatever those may be) a
special subclass in BRIVLA. I think that that should be documented
somewhere. I guess that they could be applied to non-units and simply
yield nonsense (just like the 'SI prefixes' would). For example,
"ki'orxu'e tei'a re fei'u snidu" would be "square kiloreds per second",
which is


## 2019-04-24T18:48:25Z — krtisfranks (comment 3479, on definition 66354, in reply to 3478)

Re: Clarification

> Oh, and these words essentially make units (whatever those may be) a
> special subclass in BRIVLA. I think that that should be documented
> somewhere. I guess that they could be applied to non-units and simply
> yield nonsense (just like the 'SI prefixes' would). For example,
> "ki'orxu'e tei'a re fei'u snidu" would be "square kiloreds per second",
> which is

nonsensical but grammatically proper and expressible. (It might have
meaning in a joke or something).

