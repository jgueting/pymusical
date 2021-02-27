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
                 new_scale='C/a',
                 clef='violin'):

        # an important constant value for the conversion of musical halt tone steps to frequency values
        # is the twelfth root of 2
        self.__root__ = 1.0594630943592952645618252949463  # (2 ** (1 / 12))

        # *** parser definitions ***
        # helper
        no_whites = pp.NotAny(pp.White())

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

        # cent: 100th part of a musical half tone step, sign required.
        # usually between -50 and +50, returns a number between -.5 and .5
        cent = (must_sign + no_whites + real + pp.StringEnd()).setParseAction(lambda t: t[0] * t[1] / 100)

        # helpers for the note parser
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

        # parse action for the note parser. checks if eg. "D#/Eb" contains the same note value twice and
        # returns the note value
        def note_parser_action(t):
            if len(t) > 1:
                if isinstance(t[1], int):
                    if t[0] != t[1]:
                        raise ValueError('Notes do not match!')
                    t.pop(1)
            return sum(t)

        # parses a string like "A#4 +30" into a musical half tone step + cents
        self.note_parser = (
                pp.Optional(full_note +
                            (pp.FollowedBy(no_whites + '/') +
                             no_whites + '/' +
                             pp.FollowedBy(no_whites + full_note)
                             ).suppress() + no_whites) +
                full_note + (pp.StringEnd() ^ cent)
        ).setParseAction(note_parser_action).setResultsName('note_value')

        # parses a string like "440Hz" into a frequency value
        self.hertz_parser = (
                real + 'Hz'
        ).setParseAction(lambda t: t[0]).setResultsName('frequency')


        # # parse action for score parser
        # def score_parse_action(tokens):
        #     position = tokens[0]
        #
        #     position -= self.clefs[self.clef]
        #     octave_offset = position // 7
        #     position = position % 7
        #     used_values = [-9 + i for i in range(12) if not self.keys[self.key][1][i] == ' ']
        #
        #     if len(tokens) > 1:
        #         if tokens[1] == 'b':
        #             accidental_offset = -1
        #         elif tokens[1] == '#':
        #             accidental_offset = +1
        #         elif tokens[1] == '##':
        #             accidental_offset = 2
        #         elif tokens[1] == 'bb':
        #             accidental_offset = -2
        #         elif tokens[1] in ['n', 'n#', 'nb']:
        #             vorzeichen = self.keys[self.key][1].replace(' ', '')[position]
        #             if vorzeichen not in '#b':
        #                 raise MusicConverterError('natural sign not applicable!')
        #             else:
        #                 if vorzeichen == 'b':
        #                     accidental_offset = 1
        #                     if len(tokens[1]) > 1:
        #                         if tokens[1][1] == '#':
        #                             accidental_offset = 2
        #                         else:
        #                             raise MusicConverterError('natural flat sign not applicable')
        #                 else:
        #                     accidental_offset = -1
        #                     if len(tokens[1]) > 1:
        #                         if tokens[1][1] == 'b':
        #                             accidental_offset = -2
        #                         else:
        #                             raise MusicConverterError('natural sharp sign not applicable')
        #         else:
        #             accidental_offset = 0
        #     else:
        #         accidental_offset = 0
        #
        #     return octave_offset * 12 + used_values[position] + accidental_offset
        #
        # parses a string like "sc -3:#" into a note value (musical half tone step)
        self.score_parser = (
            pp.Keyword('sc').suppress() + integer + pp.Literal(':').suppress() +
            (
                pp.Keyword('##') |
                pp.Keyword('bb') |
                # pp.Keyword('n#') |
                # pp.Keyword('nb') |
                pp.Keyword('_') |
                pp.Keyword('#') |
                pp.Keyword('b') |
                pp.Keyword('n')
            ) |
            pp.Keyword('sc').suppress() + integer + pp.LineEnd()
        ).setResultsName('notation')  # .setParseAction(score_parse_action).setResultsName('note_value')

        # parse a string like "35%" into an amplitude value
        self.amp_parser = (real + '%'
                           ).setParseAction(lambda t: t[0] / 100.).setResultsName('amplitude')

        # parse a string like "-10dB" into an amplitude value
        self.gain_parser = (may_sign + no_whites + real + no_whites + pp.Literal('dB').suppress()
                            ).setParseAction(lambda t: 10. ** (t[0] * t[1] / 20.)).setResultsName('amplitude')

        # assign a frequency to a specified note name: "A4=440Hz". Internally the frequency for A4 is calculated.
        self.base_parser = (full_note + pp.Literal('=').suppress() + self.hertz_parser
                            ).setParseAction(lambda t: t[1] * (self.__root__ ** -t[0])).setResultsName('base_freq')

        # all properties parser
        # todo: not all properties are parsed, yet
        self.input_parser = self.note_parser ^ \
                            self.hertz_parser ^ \
                            self.score_parser ^ \
                            self.base_parser ^ \
                            self.amp_parser ^ \
                            self.gain_parser

        # *** initializations ***
        self.__note_value__ = 0.
        self.__base_freq__ = 440.
        self.base_freq = base_freq

        self.key = new_scale
        self.__names__ = 'C D EF G A B'
        self.clef = clef
        self.__clef__ = 'violin'

        self.max_gain = max_gain
        self.min_gain = min_gain
        self.amplitude = amplitude

    # *** core property ***
    @property
    def note_value(self):
        """
        The note_value is the core property-value of the converter class. The whole numbers represent the keys on the
        piano keyboard, zero being the A above the middle C (A4). Float values express tones between the keys.
        :return: note value
        """
        return self.__note_value__

    @note_value.setter
    def note_value(self, new_val):
        if isinstance(new_val, str):
            try:
                new_val = self.note_parser.parseString(new_val)[0]
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
        """
        converts the converters note_value into its corresponding frequency
        using the base frequency (default is A4=440Hz)
        :return: frequency in Hz
        """
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
        """
        base frequency. note value 0 has this frequency. all other frequencies / note values are calculated
        on this base
        :return: base frequency in Hz
        """
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
        """
        this amplitude can be used by e.g. an audio app to control the loudness
        :return: amplitude as a factor 0..1
        """
        return self.__amplitude__

    @amplitude.setter
    def amplitude(self, new_amp):
        if isinstance(new_amp, str):
            try:
                new_amp = self.amp_parser.parseString(new_amp)[0]
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
        """
        a second way to look at the amplitude is gain.
        :return: gain in dB -inf..0
        """
        return 20. * log10(self.__amplitude__)

    @gain.setter
    def gain(self, new_gain):
        """
        :param new_gain: pass new gain as number (float or int) or as string to be parsed
        :return: None. gain value is converted into an amplitude value an stored this class' instance
        """
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
            raise TypeError(f'MusicConverter.gain only accepts <str>, <float>, or <int>')

    # *** properties for conversion to the musical world ***
    @property
    def octave(self):
        """
        :return: the octave the current note value is in: A4 is in octave 4
        """
        return int(ceil((round(self.note_value) - 2) / 12) + 4)

    @property
    def note_name(self):
        """
        :return: name of the current note value as string
        """
        steps = int(round(self.note_value))
        octave = self.octave
        note_names = {
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
        name = note_names[steps - (octave - 4) * 12]

        cents = str(int(round((self.note_value - steps) * 100)))
        cents_str = '' if cents == '0' else '+' + cents if not cents.startswith('-') else cents

        return ' '.join([name, cents_str]).strip()

    @note_name.setter
    def note_name(self, new_name):
        """
        converts a given note name into a note value, the note value is stored in this class' instance
        :param new_name: name of new note
        """
        if isinstance(new_name, str):
            try:
                self.__note_value__ = self.note_parser.parseString(new_name)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_name}" @ col {e.col}!')
        else:
            raise TypeError('MusicConverter.note_name only accepts <str>')

    @property
    def key(self):
        """
        :return: the current key used to calc key_name and notation
        """
        return self.__key__

    @key.setter
    def key(self, new_key):
        if new_key in self.keys:
            self.__key__ = new_key
        else:
            keys = '", "'.join([exiting_key for exiting_key in self.keys])
            raise MusicConverterError(f'<key> must be one of "{keys}"')

    @property
    def key_name(self):
        used_ivories = self.keys[self.key][1][:]
        amendment = ''
        note_octave_index = int(round(self.note_value) + 9)
        if used_ivories[note_octave_index] == 'b':
            note_octave_index += 1
            amendment = 'b'
        elif used_ivories[note_octave_index] == '#':
            note_octave_index -= 1
            amendment = '#'
        else:
            if self.__names__[note_octave_index] == ' ':
                if 'b' in used_ivories:
                    note_octave_index += 1
                    amendment = 'b'
                else:
                    note_octave_index -= 1
                    amendment = '#'

        return f'{self.__names__[note_octave_index % 12]}{amendment}{self.octave}'

    @property
    def keys(self):
        """
        available keys
        :return: dict of available keys mapping some internal conversion data
        """
        return {
            'C/a':    (0, '_ _ __ _ _ _'),
            'F/d':    (1, '_ _ __ _ _b '),
            'Bb/g':   (2, '_ _b _ _ _b '),
            'Eb/c':   (3, '_ _b _ _b b '),
            'Ab/f':   (4, '_b b _ _b b '),
            'Db/bb':  (5, '_b b _b b b '),
            'C#/a#':  (5, '## # ## # # '),
            'F#/d#':  (6, ' # # ## # #_'),
            'Gb/eb':  (6, ' b bb_b b b '),
            'B/g#':   (7, ' # #_ # # #_'),
            'Cb/ab':  (7, ' b bb b b bb'),
            'E/c#':   (8, ' # #_ # #_ _'),
            'A/f#':   (9, ' #_ _ # #_ _'),
            'D/b':   (10, ' #_ _ #_ _ _'),
            'G/e':   (11, '_ _ _ #_ _ _')
        }

    @property
    def notation(self):
        """
        based on the current key and clef the note value is converted into a notation (head position and accidental)
        :return: tuple(head_position, accidental)
        """
        # basic (C/a) note values
        values = [-9, -7, -5, -4, -2, 0, 2]


        # calc the head position of the C of the current octave
        head_offset = (self.octave - 4) * 7 + self.clefs[self.clef]

        # actual note values
        key_accidentals = self.keys[self.key][1].replace(' ', '')
        key_offset = [1 if c == '#' else -1 if c == 'b' else 0 for c in key_accidentals]
        key_offset.append(key_offset[0])
        values = [values[i] + key_offset[i] for i in range(7)]
        values.append(values[0] + 12)

        # calc the index of the current note value within the current octave (C=0)
        note_index_in_octave = int((round(self.note_value) + 9) % 12) -9

        # signs
        acc = {
            -2: 'bb',
            -1: 'b',
             0: 'n',
             1: '#',
             2: '##'
        }

        # adjust the head position according to the note_index_in_octave
        try:
            if note_index_in_octave == values[6] - 12:
                note_index_in_octave += 12
                head_offset -= 7
            head_position = values.index(note_index_in_octave)
            notation = [(head_offset + head_position, '_')]
        except ValueError:
            for i in range(8):
                if values[i] > note_index_in_octave:
                    break
            head_position = i
            notation = [(head_offset + head_position - 1, acc[key_offset[head_position - 1] + 1]),
                        (head_offset + head_position, acc[key_offset[head_position] - 1])]
        return notation

    @notation.setter
    def notation(self, new_score):
        """
        parses a string like "sc 5:#" and converts it into the note value based on the current key and clef.
        now accepts also tuple like (5, '#') or list like [5, '#'] or int like 5 (epuivalent to "sc 5" or "sc 5:_")
        :param new_score: string holding the head position and accidental
        """
        # input verification
        signs = ['##', '#', 'n', '_', 'b', 'bb']
        if isinstance(new_score, str):
            try:
                new_score = self.score_parser.parseString(new_score)[0]
            except pp.ParseException as e:
                raise MusicConverterError(f'Could not parse "{new_score}" @ col {e.col}!')
        elif isinstance(new_score, list):
            if len(new_score) < 2:
                new_score.append('_')
            new_score = tuple(new_score)
        elif isinstance(new_score, int):
            new_score = (new_score, '_')

        if isinstance(new_score, tuple):
            if len(new_score) == 2 and isinstance(new_score[0], int) and isinstance(new_score[1], str) \
                    and new_score[1] in signs:
                score = new_score
            else:
                raise MusicConverterError(f"MusicConverter.notation must be formed (<head position>, <accidental>) e.g (-7, '_') "
                                          f"with accidental in {signs}")
        else:
            raise TypeError(f'MusicConverter.notation only accepts <str>, <int>, <list>, or <tuple> ( is <{type(new_score).__name__}>: {new_score})')

        # calculation
        head_position, acc = score
        base_pos = head_position - self.clefs[self.clef]
        octave = base_pos // 7 + 4
        head_index_in_octave = base_pos % 7

        # calc note value
        values = [-9, -7, -5, -4, -2, 0, 2]  # C/a - values
        key_accidentals = self.keys[self.key][1].replace(' ', '')
        key_offset = [1 if c == '#' else -1 if c == 'b' else 0 for c in key_accidentals]
        key_offset.append(key_offset[0])
        values = [values[i] + key_offset[i] for i in range(7)]

        note_index_in_octave = values[head_index_in_octave]
        octave_c_value = (octave - 4) * 12
        head_note_value = note_index_in_octave + octave_c_value

        # calc accidental offset
        vorzeichen = key_accidentals[head_index_in_octave]
        acc_offset = 0
        if acc == '_':
            pass
        elif acc == 'n' and vorzeichen in ['b', '#']:
            if vorzeichen == 'b':
                acc_offset = 1
            else:
                acc_offset = -1
        elif acc in ['b', '#'] and vorzeichen == '_':
            if acc == 'b':
                acc_offset = -1
            else:
                acc_offset = 1
        elif acc == 'bb' and vorzeichen == 'b':
            acc_offset = -1
        elif acc == '##' and vorzeichen == '#':
            acc_offset = 1
        else:
            raise MusicConverterError(f"<{acc}> not applicable with <{vorzeichen}> in key {self.key}!")

        self.note_value = head_note_value + acc_offset



    @property
    def clefs(self):
        """
        available clefs
        :return: dict holding the available clefs and corresponding offsets for the notation-conversion
        """
        return {
            'violin': -6,
            'alto': 0,
            'bass': +6
        }

    @property
    def clef(self):
        """
        current clef
        :return: current clef as string
        """
        return self.__clef__

    @clef.setter
    def clef(self, new_clef):
        if isinstance(new_clef, str):
            if new_clef in self.clefs:
                self.__clef__ = new_clef
            else:
                raise MusicConverterError(f'no clef with name "{new_clef}" available!')
        else:
            raise TypeError('MusicConverter.clef only accepts <str>')

    def set(self, input):
        """
        use the classes parsers to set the classes properties
        :param input:
        :return:
        """
        if isinstance(input, str):
            try:
                result = self.input_parser.parseString(input).asDict()
            except pp.ParseException as e:
                raise MusicConverterError(f'<input_parser> could not parse "{input}" @ col {e.col}; ')
            print(result)
            for attribute in result:
                setattr(self, attribute, result[attribute])
        else:
            raise TypeError('MusicConverter.set() only accepts <str> as input')
