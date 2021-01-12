import pyparsing as pp
from math import log10, ceil


class MusicConverterError(Exception):
    pass


class MusicConverter:
    def __init__(self,
                 base_freq=440.0,
                 amplitude=.5,
                 max_gain=10.,
                 min_gain=-200.,
                 scale='C/a',
                 clef='violin'):

        self.__root__ = 2 ** (1 / 12)

        # *** parser definitions ***
        no_whites = pp.NotAny(pp.White())

        real = pp.Combine(
            pp.Word(pp.nums) + pp.Optional(pp.Char(',.') + pp.Word(pp.nums))
        ).setParseAction(lambda t: float(t[0].replace(',', '.')))

        must_operator = pp.Char('+-').setParseAction(lambda t: float(t[0] + '1'))
        may_operator = pp.Optional(pp.Char('+-')).setParseAction(lambda t: float(t[0] + '1' if len(t) > 0 else '1'))

        cent = (must_operator + no_whites + real + pp.StringEnd()).setParseAction(lambda t: t[0] * t[1] / 100)

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

        def note_parser_action(t):
            if len(t) > 1:
                if isinstance(t[1], int):
                    if t[0] != t[1]:
                        raise ValueError('Notes do not match!')
                    t.pop(1)
            return sum(t)

        self.note_parser = (
                pp.Optional(full_note +
                            (pp.FollowedBy(no_whites + '/') +
                             no_whites + '/' +
                             pp.FollowedBy(no_whites + full_note)
                             ).suppress() + no_whites) +
                full_note + (pp.StringEnd() ^ cent)
        ).setParseAction(note_parser_action).setResultsName('note_value')

        self.hertz_parser = (
                real + 'Hz'
        ).setParseAction(lambda t: self.base_freq * (self.__root__ ** t[0])).setResultsName('note_value')

        # ToDo: score_parser
        # self.score_parser =

        self.note_value_parser = self.note_parser ^ self.hertz_parser

        self.amp_parser = (real + '%'
                           ).setParseAction(lambda t: t[0] / 100.).setResultsName('amplitude')

        self.gain_parser = (may_operator + no_whites + real + no_whites + pp.Literal('dB').suppress()
                            ).setParseAction(lambda t: 10. ** (t[0] * t[1] / 20.)).setResultsName('amplitude')

        self.base_parser = (full_note + pp.Literal('=').suppress() + self.hertz_parser
                            ).setParseAction(lambda t: t[1] * (self.__root__ ** -t[0])).setResultsName('base_freq')

        self.input_parser = self.note_value_parser ^ self.base_parser ^ self.amp_parser ^ self.gain_parser

        # *** initializations ***
        self.__note_value__ = 0.
        self.__base_freq__ = 440.
        self.base_freq = base_freq

        self.scale = scale
        self.clef = clef

        self.max_gain = max_gain
        self.min_gain = min_gain
        self.amplitude = amplitude

    # *** core property ***
    @property
    def note_value(self):
        """
        The note_value is the core property-value of the converter class. The whole numbers represent the keys on the
        piano keyboard, zero being the A above the middle C (A4). Float values express tones between the keys.
        """
        return self.__note_value__

    @note_value.setter
    def note_value(self, new_val):
        if isinstance(new_val, str):
            try:
                new_val = self.note_value_parser.parseString(new_val)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_val}" @ col {e.col}!')

        if isinstance(new_val, (int, float)):
            if -58. <= new_val <= 66.:  # roughly corresponds to 16..20000Hz if A4=440Hz
                self.__note_value__ = new_val
            else:
                raise MusicConverterError(f'<note_value> out of audible range!')
        else:
            raise TypeError('MusicConverter.note_value only accepts <str>, <float>, or <int>')

    # *** properties for conversion to the physical world ***
    @property
    def frequency(self):
        return self.base_freq * (self.__root__ ** self.__note_value__)

    @frequency.setter
    def frequency(self, new_freq):
        if isinstance(new_freq, str):
            try:
                new_freq = self.hertz_parser.parseString(new_freq)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_freq}" @ col {e.col}!')
        if isinstance(new_freq, (int, float)):
            if 16. <= new_freq <= 20000.:
                self.__note_value__ = log10(new_freq / self.__base_freq__) / log10(self.__root__)
            else:
                raise MusicConverterError(f'<frequency> out of audible range!')
        else:
            raise TypeError('MusicConverter.frequency only accepts <str>, <float>, or <int>')


    @property
    def base_freq(self):
        return self.__base_freq__

    @base_freq.setter
    def base_freq(self, new_freq):
        if isinstance(new_freq, str):
            try:
                new_freq = (self.base_parser ^ self.hertz_parser).parseString(new_freq)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_freq}" @ col {e.col}!')
        if isinstance(new_freq, (int, float)):
            if 16. <= new_freq <= 20000.:
                self.__note_value__ = log10(new_freq / self.__base_freq__) / log10(self.__root__)
            else:
                raise MusicConverterError(f'<base_freq> out of audible range!')
        else:
            raise TypeError('MusicConverter.base_freq only accepts <str>, <float>, or <int>')

    @property
    def amplitude(self):
        return self.__amplitude__

    @amplitude.setter
    def amplitude(self, new_amp):
        if isinstance(new_amp, str):
            try:
                new_freq = self.amp_parser.parseString(new_amp)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_amp}" @ col {e.col}!')
        if isinstance(new_amp, (int, float)):
            if 0. <= new_amp <= 1.:
                self.__amplitude__ = new_amp
            else:
                raise MusicConverterError(f'<amplitude> out of range!')
        else:
            raise TypeError('MusicConverter.amplitude only accepts <str>, <float>, or <int>')

    @property
    def gain(self):
        return 20. * log10(self.__amplitude__)

    @gain.setter
    def gain(self, new_gain):
        if isinstance(new_gain, str):
            try:
                self.__amplitude__ = self.gain_parser.parseString(new_gain)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_gain}" @ col {e.col}!')
        elif isinstance(new_gain, (int, float)):
            if new_gain <= 0.:
                self.__amplitude__ = 10. ** (new_gain / 20.)
            else:
                raise MusicConverterError(f'maximum <gain> is 0.0dB')
        else:
            raise TypeError(f'new_amp must be int, float, or str!')

    # *** properties for conversion to the musical world ***
    @property
    def octave(self):
        return int(ceil((round(self.note_value) - 2) / 12) + 4)

    @property
    def note_name(self):
        steps = int(round(self.note_value))
        octave = self.octave
        names = {
            -9: f'C{octave}',
            -8: f'C#{octave}/Db{octave}',
            -7: f'D{octave}',
            -6: f'D#{octave}/Eb{octave}',
            -5: f'E{octave}',
            -4: f'F{octave}',
            -3: f'F#{octave}/Gb{octave}',
            -2: f'G{octave}',
            -1: f'G#{octave}/Ab{octave}',
            0: f'A{octave}',
            1: f'A#{octave}/Bb{octave}',
            2: f'B{octave}'
        }
        name = names[steps - (octave - 4) * 12]

        cents = str(int(round((self.note_value - steps) * 100)))
        cents_str = '' if cents == '0' else '+' + cents if not cents.startswith('-') else cents

        return ' '.join([name, cents_str]).strip()

    @note_name.setter
    def note_name(self, new_name):
        if isinstance(new_name, str):
            try:
                self.__note_value__ = self.note_parser.parseString(new_name)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_name}" @ col {e.col}!')
        else:
            raise TypeError('MusicConverter.note_name only accepts <str>')

    @property
    def scale(self):
        return self.__scale__

    @scale.setter
    def scale(self, new_scale):
        if new_scale in self.scales:
            self.__scale__ = new_scale
        else:
            scales = '", "'.join([scale for scale in self.scales])
            raise MusicConverterError(f'<scale> must be one of "{scales}"')

    @property
    def scale_name(self):
        return self.scales[self.scale][1][int(self.note_value - 3) % 12]

    @property
    def scales(self):
        scales = {
            'C/a': (0,
                    ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'],
                    ['_', '#', '_', '#', '_', '_', '#', '_', '#', '_', '#', '_'],
                    '#'),
            'F/d': (1,
                    ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'],
                    ['_', 'b', '_', 'b', '_', '_', 'b', '_', 'b', '_', '_', 'n'],
                    'b'),
            'Bb/g': (2,
                     ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'],
                     ['_', 'b', '_', '_', 'n', '_', 'b', '_', 'b', '_', '_', 'n'],
                     'b'),
            'Eb/c': (3,
                     ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'],
                     ['_', 'b', '_', '_', 'n', '_', 'b', '_', '_', 'n', '_', 'n'],
                     'b'),
            'Ab/f': (4,
                     ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'],
                     ['_', '_', 'n', '_', 'n', '_', 'b', '_', '_', 'n', '_', 'n'],
                     'b'),
            'Db/bb': (5,
                      ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'],
                      ['_', '_', 'n', '_', 'n', '_', '_', 'n', '_', 'n', '_', 'n'],
                      'b'),
            'C#/a#': (5,
                      ['B#', 'C#', 'D', 'D#', 'E', 'E#', 'F#', 'G', 'G#', 'A', 'A#', 'B'],
                      ['_', '_', 'n', '_', 'n', '_', '_', 'n', '_', 'n', '_', 'n'],
                      '#'),
            'F#/d#': (6,
                      ['C', 'C#', 'D', 'D#', 'E', 'E#', 'F#', 'G', 'G#', 'A', 'A#', 'B'],
                      ['n', '_', 'n', '_', 'n', '_', '_', 'n', '_', 'n', '_', '_'],
                      '#'),
            'Gb/eb': (6,
                      ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'Cb'],
                      ['n', '_', 'n', '_', 'n', '_', '_', 'n', '_', 'n', '_', '_'],
                      'b'),
            'B/g#': (7,
                     ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'],
                     ['n', '_', 'n', '_', '_', 'n', '_', 'n', '_', 'n', '_', '_'],
                     '#'),
            'Cb/ab': (7,
                      ['C', 'Db', 'D', 'Eb', 'Fb', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'Cb'],
                      ['n', '_', 'n', '_', '_', 'n', '_', 'n', '_', 'n', '_', '_'],
                      'b'),
            'E/c#': (8,
                     ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'],
                     ['n', '_', 'n', '_', '_', 'n', '_', 'n', '_', '_', '#', '_'],
                     '#'),
            'A/f#': (9,
                     ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'],
                     ['n', '_', '_', '#', '_', 'n', '_', 'n', '_', '_', '#', '_'],
                     '#'),
            'D/b': (10,
                    ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'],
                    ['n', '_', '_', '#', '_', 'n', '_', '_', '#', '_', '#', '_'],
                    '#'),
            'G/e': (11,
                    ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'],
                    ['_', '#', '_', '#', '_', 'n', '_', '_', '#', '_', '#', '_'],
                    '#')
        }
        return scales

    @property
    def score(self):
        return f'{self.score_pos}:{self.score_acc}'

    @score.setter
    def score(self, new_score):
        if isinstance(new_score, str):
            try:
                self.__note_value__ = self.score.parseString(new_score)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_score}" @ col {e.col}!')
        else:
            raise TypeError('MusicConverter.score only accepts <str>')

    @property
    def score_pos(self):
        return 0

    @property
    def score_acc(self):
        return '_'
