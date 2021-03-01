import pyparsing as pp

# *** parser definitions ***
# helper
no_whites = pp.NotAny(pp.White())
tok_end = (pp.StringEnd() | pp.LineEnd()).suppress()

# numbers
real = pp.Combine(
    pp.Word(pp.nums) + pp.Optional(pp.Char(',.') + pp.Word(pp.nums))
).setParseAction(lambda t: float(t[0].replace(',', '.')))

integer = (
        pp.Optional(pp.Literal('-')) + pp.Word(pp.nums)
).setParseAction(lambda t: int(t[0] + t[1]) if len(t) > 1 else int(t[0]))

# signs
must_sign = pp.Char('+-').setParseAction(lambda t: float(t[0] + '1'))
may_sign = pp.Optional(pp.Char('+-')).setParseAction(lambda t: float(t[0] + '1' if len(t) > 0 else '1'))

# note value cents
cent = (must_sign + no_whites + real).setParseAction(lambda t: t[0] * t[1] / 100)

# helpers for the note name parser
note_name_offset = {
    'C': -9,
    'D': -7,
    'E': -5,
    'F': -4,
    'G': -2,
    'A': 0,
    'B': 2,
}
note_name = pp.Char('CDEFGABcdefgab').setParseAction(
    lambda t: note_name_offset[t[0] if t[0] in 'CDEFGAB' else t[0].upper()]
)

flat_sharp = pp.Char('#b').setParseAction(lambda t: 1 if t[0] == '#' else -1)
octave = pp.Char('0123456789').setParseAction(lambda t: (int(t[0]) - 4) * 12)
full_note = (note_name + no_whites + pp.Optional(pp.FollowedBy(flat_sharp) + flat_sharp)
             + no_whites + pp.FollowedBy(octave) + octave
             ).setParseAction(lambda t: sum(t))

note_name_parser = (
    full_note + pp.Optional(pp.White()).suppress() + pp.Optional(cent) + tok_end
).setParseAction(lambda t:float(sum(t))).setResultsName('note_value')

# frequency parsers
hertz = real + pp.Literal('Hz').suppress()

frequency_parser = (
    hertz + tok_end
).setParseAction(lambda t: float(t[0])).setResultsName('frequency')

base_freq_parser = (
    full_note + pp.Literal('=').suppress() + hertz + tok_end
).setParseAction(lambda t: t[1] * (1.0594630943592952645618252949463 ** -t[0])).setResultsName('base_freq')

# parses a string like "sc -7:b" into a musical half tone step (using the MusicConverter.set method)
sign = (pp.Keyword('##') | pp.Keyword('bb') | pp.Keyword('#') | pp.Keyword('b') | pp.Keyword('n') | pp.Keyword('_'))
score_parser = (
    integer + pp.Literal(':').suppress() + sign + tok_end
).setResultsName('notation')

# amplitude parser
amp_parser = (
    real + pp.Literal('%').suppress() + tok_end
).setParseAction(lambda t: float(t[0])).setResultsName('amplitude')

gain_parser = (
    may_sign + real + pp.Literal('dB').suppress() + tok_end
).setParseAction(lambda t: 10. ** (t[0] * t[1] / 20.)).setResultsName('amplitude')

# clef parser
clef_parser = (
    pp.Keyword('violin') | pp.Keyword('alto') | pp.Keyword('bass')
).setResultsName('clef')

# key parser
keys = {
    'C/a':    (0, '_ _ __ _ _ _'),
    'F/d':    (1, '_ _ __ _ _b '),
    'Bb/g':   (2, '_ _b _ _ _b '),
    'Eb/c':   (3, '_ _b _ _b b '),
    'Ab/f':   (4, '_b b _ _b b '),
    'Db/bb':  (5, '_b b _b b b '),
    'C#/a#':  (5, '## # ## # # '),
    'F#/d#':  (6, ' # # ## # #_'),
    'Gb/eb':  (6, ' b b _b b bb'),
    'B/g#':   (7, ' # #_ # # #_'),
    'Cb/ab':  (7, ' b bb b b bb'),
    'E/c#':   (8, ' # #_ # #_ _'),
    'A/f#':   (9, ' #_ _ # #_ _'),
    'D/b':   (10, ' #_ _ #_ _ _'),
    'G/e':   (11, '_ _ _ #_ _ _')
}

key_token = pp.NoMatch()

for key in keys:
    key_token = key_token | pp.Keyword(key)

key_parser = (
    key_token
).setResultsName('key')

# complete parser
input_parser = note_name_parser | \
               frequency_parser | \
               base_freq_parser | \
               amp_parser | \
               gain_parser | \
               clef_parser | \
               key_parser | \
               score_parser


if __name__ == '__main__':
    print('*** ParserTest ***\n')
    in_str = ''
    while not in_str == 'quit':
        in_str = input('>> ')
        if not in_str == 'quit':
            try:
                result = input_parser.parseString(in_str).asDict()
                print(result)
            except pp.ParseException as err:
                print(f'parse error @ col{err.col}: {err}')
        else:
            print('terminated.')