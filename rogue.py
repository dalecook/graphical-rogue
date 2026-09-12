#!/usr/bin/env python3
"""
Rogue -- Exploring the Dungeons of Doom.  A graphical pygame port.

This is a faithful port of the authentic Rogue 5.4.5 C source released by the
Roguelike Restoration Project, which is the final UNIX version of the original
game by Michael Toy, Ken Arnold and Glenn Wichman.  The dungeon generator, the
monster tables, the combat formulas, the item probabilities and the daemon/fuse
scheduler are all carried across value-for-value from that C source; what is new
here is the presentation layer, which replaces curses with a pygame tile grid.

Run it:

    py -3.13 rogue.py                  play
    py -3.13 rogue.py --seed 42        reproducible dungeon
    py -3.13 rogue.py --selftest 2000  headless soak test, exits nonzero on error

Requires pygame and nothing else.  No data files, no images, no external fonts.

----------------------------------------------------------------------------
Rogue: Exploring the Dungeons of Doom
Copyright (C) 1980-1983, 1985, 1999 Michael Toy, Ken Arnold and Glenn Wichman
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.
3. Neither the name(s) of the author(s) nor the names of other contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR(S) AND CONTRIBUTORS ``AS IS'' AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR(S) OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
SUCH DAMAGE.
----------------------------------------------------------------------------
"""

import os
import sys
import random
import argparse
import traceback

import pygame

# ---------------------------------------------------------------------------
# Constants, ported from rogue.h
# ---------------------------------------------------------------------------

RELEASE = "5.4.5"
VERSION = "rogue (pygame port) of rogue 5.4.5"

MAXDAEMONS = 20                 # rogue.h:19
EMPTY = 0

MAXROOMS = 9                    # rogue.h:26
MAXTHINGS = 9
MAXOBJ = 9
MAXPACK = 23
MAXTRAPS = 10
AMULETLEVEL = 26
NUMTHINGS = 7                   # number of types of things
MAXPASS = 13                    # upper limit on number of passages
NUMLINES = 24
NUMCOLS = 80
STATLINE = NUMLINES - 1
BORE_LEVEL = 50

# The C stores the map in a flat array indexed ((x) << 5) + y, i.e. a stride of
# 32 rows per column.  rogue.h:76  #define INDEX(y,x) (&places[((x)<<5)+(y)])
MAXLINES = 32
MAXCOLS = 80

# return values for get functions              rogue.h:39
NORM, QUIT, MINUS = 0, 1, 2

# inventory types                              rogue.h:46
INV_OVER, INV_SLOW, INV_CLEAR = 0, 1, 2

# things that appear on the screen             rogue.h:85
PASSAGE = '#'
DOOR = '+'
FLOOR = '.'
PLAYER = '@'
TRAP = '^'
STAIRS = '%'
GOLD = '*'
POTION = '!'
SCROLL = '?'
MAGIC = '$'
FOOD = ':'
WEAPON = ')'
ARMOR = ']'
AMULET = ','
RING = '='
STICK = '/'
VWALL = '|'
HWALL = '-'
SPACE = ' '
CALLABLE = -1
R_OR_S = -2

# Various constants                            rogue.h:107
# BEARTIME/SLEEPTIME/etc are spread(n) in the C -- see spread() below.
HEALTIME = 30
HUHDURATION = 20
SEEDURATION = 850
HUNGERTIME = 1300
MORETIME = 150
STOMACHSIZE = 2000
STARVETIME = 850
ESCAPE = 27
LEFT, RIGHT = 0, 1
BOLT_LENGTH = 6
LAMPDIST = 3

# Save against things                          rogue.h:139
VS_POISON = 0o00
VS_PARALYZATION = 0o00
VS_DEATH = 0o00
VS_BREATH = 0o02
VS_MAGIC = 0o03

# flags for rooms                              rogue.h:149
ISDARK = 0o000001
ISGONE = 0o000002
ISMAZE = 0o000004

# flags for objects                            rogue.h:154
ISCURSED = 0o000001
ISKNOW = 0o000002
ISMISL = 0o000004
ISMANY = 0o000010
ISPROT = 0o000040

# flags for creatures                          rogue.h:162
# NOTE: several of these deliberately share bit values in the original --
# ISCANC/ISLEVIT (0o10) and ISMEAN/ISHALU (0o4000) and SEEMONST/ISFLY (0o40000).
# The C gets away with it because the overlapping pairs never apply to the same
# kind of thing (hero vs monster).  Ported as-is.
CANHUH = 0o000001
CANSEE = 0o000002
ISBLIND = 0o000004
ISCANC = 0o000010
ISLEVIT = 0o000010
ISFOUND = 0o000020
ISGREED = 0o000040
ISHASTE = 0o000100
ISTARGET = 0o000200
ISHELD = 0o000400
ISHUH = 0o001000
ISINVIS = 0o002000
ISMEAN = 0o004000
ISHALU = 0o004000
ISREGEN = 0o010000
ISRUN = 0o020000
SEEMONST = 0o040000
ISFLY = 0o040000
ISSLOW = 0o100000

# Flags for level map                          rogue.h:182
F_PASS = 0x80                   # is a passageway
F_SEEN = 0x40                   # have seen this spot before
F_DROPPED = 0x20                # object was dropped here
F_LOCKED = 0x20                 # door is locked
F_REAL = 0x10                   # what you see is what you get
F_PNUM = 0x0f                   # passage number mask
F_TMASK = 0x07                  # trap number mask

# Trap types                                   rogue.h:192
T_DOOR = 0o0
T_ARROW = 0o1
T_SLEEP = 0o2
T_BEAR = 0o3
T_TELEP = 0o4
T_DART = 0o5
T_RUST = 0o6
T_MYST = 0o7
NTRAPS = 8

# Potion types                                 rogue.h:205
P_CONFUSE = 0
P_LSD = 1
P_POISON = 2
P_STRENGTH = 3
P_SEEINVIS = 4
P_HEALING = 5
P_MFIND = 6
P_TFIND = 7
P_RAISE = 8
P_XHEAL = 9
P_HASTE = 10
P_RESTORE = 11
P_BLIND = 12
P_LEVIT = 13
MAXPOTIONS = 14

# Scroll types                                 rogue.h:224
S_CONFUSE = 0
S_MAP = 1
S_HOLD = 2
S_SLEEP = 3
S_ARMOR = 4
S_ID_POTION = 5
S_ID_SCROLL = 6
S_ID_WEAPON = 7
S_ID_ARMOR = 8
S_ID_R_OR_S = 9
S_SCARE = 10
S_FDET = 11
S_TELEP = 12
S_ENCH = 13
S_CREATE = 14
S_REMOVE = 15
S_AGGR = 16
S_PROTECT = 17
MAXSCROLLS = 18

# Weapon types                                 rogue.h:249
MACE = 0
SWORD = 1
BOW = 2
ARROW = 3
DAGGER = 4
TWOSWORD = 5
DART = 6
SHIRAKEN = 7
SPEAR = 8
FLAME = 9                       # fake entry for dragon breath (ick)
MAXWEAPONS = 9                  # this should equal FLAME
NO_WEAPON = -1                  # PORT NOTE: C uses a NULL launcher pointer

# Armor types                                  rogue.h:265
LEATHER = 0
RING_MAIL = 1
STUDDED_LEATHER = 2
SCALE_MAIL = 3
CHAIN_MAIL = 4
SPLINT_MAIL = 5
BANDED_MAIL = 6
PLATE_MAIL = 7
MAXARMORS = 8

# Ring types                                   rogue.h:277
R_PROTECT = 0
R_ADDSTR = 1
R_SUSTSTR = 2
R_SEARCH = 3
R_SEEINVIS = 4
R_NOP = 5
R_AGGR = 6
R_ADDHIT = 7
R_ADDDAM = 8
R_REGEN = 9
R_DIGEST = 10
R_TELEPORT = 11
R_STEALTH = 12
R_SUSTARM = 13
MAXRINGS = 14

# Rod/Wand/Staff types                         rogue.h:295
WS_LIGHT = 0
WS_INVIS = 1
WS_ELECT = 2
WS_FIRE = 3
WS_COLD = 4
WS_POLYMORPH = 5
WS_MISSILE = 6
WS_HASTE_M = 7
WS_SLOW_M = 8
WS_DRAIN = 9
WS_NOP = 10
WS_TELAWAY = 11
WS_TELTO = 12
WS_CANCEL = 13
MAXSTICKS = 14

# Hunger states                                daemons.c / rogue.h
F_OKAY = 0
F_HUNGRY = 1
F_WEAK = 2
F_FAINT = 3

HUNGER_NAMES = ["", "Hungry", "Weak", "Faint"]

# Daemon slot type                             daemon.c
DAEMON = -1
FUSE = -2


# Mechanical transcription of the Rogue 5.4.5 monster tables.
# Sources (reference/rogue5.4/):
#   rogue.h    - flag bit #defines, struct monster, struct stats
#   extern.c   - struct monster monsters[26] (the table itself lives here, NOT monsters.c)
#   monsters.c - lvl_mons[] / wand_mons[] selection tables
# Values are byte-for-byte from the C. Do not "fix" anything here.

# ---------------------------------------------------------------------------
# Flag bits.  The C uses octal literals; hex equivalents given.
# Three separate namespaces reuse the same bit values (rooms, objects,
# creatures), so identical numbers below are NOT duplicates.
# ---------------------------------------------------------------------------

# flags for rooms
ISDARK = 0x0001    # 0000001 room is dark                    # rogue.h:149
ISGONE = 0x0002    # 0000002 room is gone (a corridor)       # rogue.h:150
ISMAZE = 0x0004    # 0000004 room is gone (a corridor)       # rogue.h:151

# flags for objects
ISCURSED = 0x0001  # 000001  object is cursed                # rogue.h:154
ISKNOW = 0x0002    # 0000002 player knows details about the object  # rogue.h:155
ISMISL = 0x0004    # 0000004 object is a missile type        # rogue.h:156
ISMANY = 0x0008    # 0000010 object comes in groups          # rogue.h:157
# ISFOUND 0000020  ...is used for both objects and creatures # rogue.h:158
ISPROT = 0x0020    # 0000040 armor is permanently protected  # rogue.h:159

# flags for creatures
CANHUH = 0x0001    # 0000001 creature can confuse            # rogue.h:162
CANSEE = 0x0002    # 0000002 creature can see invisible creatures   # rogue.h:163
ISBLIND = 0x0004   # 0000004 creature is blind               # rogue.h:164
ISCANC = 0x0008    # 0000010 creature has special qualities cancelled  # rogue.h:165
ISLEVIT = 0x0008   # 0000010 hero is levitating              # rogue.h:166
ISFOUND = 0x0010   # 0000020 creature has been seen (used for objects)  # rogue.h:167
ISGREED = 0x0020   # 0000040 creature runs to protect gold   # rogue.h:168
ISHASTE = 0x0040   # 0000100 creature has been hastened      # rogue.h:169
ISTARGET = 0x0080  # 000200  creature is the target of an 'f' command  # rogue.h:170
ISHELD = 0x0100    # 0000400 creature has been held          # rogue.h:171
ISHUH = 0x0200     # 0001000 creature is confused            # rogue.h:172
ISINVIS = 0x0400   # 0002000 creature is invisible           # rogue.h:173
ISMEAN = 0x0800    # 0004000 creature can wake when player enters room  # rogue.h:174
ISHALU = 0x0800    # 0004000 hero is on acid trip            # rogue.h:175
ISREGEN = 0x1000   # 0010000 creature can regenerate         # rogue.h:176
ISRUN = 0x2000     # 0020000 creature is running at the player  # rogue.h:177
SEEMONST = 0x4000  # 040000  hero can detect unseen monsters # rogue.h:178
ISFLY = 0x4000     # 0040000 creature can fly                # rogue.h:179
ISSLOW = 0x8000    # 0100000 creature has been slowed        # rogue.h:180

# ---------------------------------------------------------------------------
# MONSTERS - extern.c:190-221, in table order (index 0 == 'A').
#   "ch"    chr(ord('A') + index), matching monsters[tp->t_type - 'A'] in C.
#   "carry" m_carry, percent chance of carrying treasure.
#   "flags" m_flags, the OR'd expression from the table.
#   str/exp/lvl/arm/hpt/dmg  are m_stats (struct stats, rogue.h:362-370).
#
# In extern.c the table is written with two local macros:
#   #define ___ 1   (extern.c:188)  -> every monster's s_hpt is the int 1
#   #define XX 10   (extern.c:189)  -> every monster's s_str is the int 10
# s_hpt is an int in 5.4.5, not a dice string; actual HP is rolled in
# new_monster() as roll(s_lvl, 8) (monsters.c:77), so the stored 1 is unused.
# s_dmg uses 'x' as the dice separator in 5.4.5 (e.g. "1x8" == 1d8);
# strings are reproduced exactly as written in the C.
# ---------------------------------------------------------------------------

MONSTERS = [
    {
        "ch": "A",
        "name": "aquator",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 20,
        "lvl": 5,
        "arm": 2,
        "hpt": 1,
        "dmg": "0x0/0x0",
    },  # extern.c:193
    {
        "ch": "B",
        "name": "bat",
        "carry": 0,
        "flags": ISFLY,
        "str": 10,
        "exp": 1,
        "lvl": 1,
        "arm": 3,
        "hpt": 1,
        "dmg": "1x2",
    },  # extern.c:194
    {
        "ch": "C",
        "name": "centaur",
        "carry": 15,
        "flags": 0,
        "str": 10,
        "exp": 17,
        "lvl": 4,
        "arm": 4,
        "hpt": 1,
        "dmg": "1x2/1x5/1x5",
    },  # extern.c:195
    {
        "ch": "D",
        "name": "dragon",
        "carry": 100,
        "flags": ISMEAN,
        "str": 10,
        "exp": 5000,
        "lvl": 10,
        "arm": -1,
        "hpt": 1,
        "dmg": "1x8/1x8/3x10",
    },  # extern.c:196
    {
        "ch": "E",
        "name": "emu",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 2,
        "lvl": 1,
        "arm": 7,
        "hpt": 1,
        "dmg": "1x2",
    },  # extern.c:197
    {
        "ch": "F",
        "name": "venus flytrap",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 80,
        "lvl": 8,
        "arm": 3,
        "hpt": 1,
        # C literal is "%%%x0"; the NOTE at extern.c:199-200 says the %%% only
        # exists to stop xstr merging the string, because the program writes
        # over it: fight.c:272 sprintf's "%dx1" with an increasing hit count,
        # and fight.c:644 / wizard.c:225 reset it to "000x0".
        "dmg": "%%%x0",
    },  # extern.c:198
    {
        "ch": "G",
        "name": "griffin",
        "carry": 20,
        "flags": ISMEAN | ISFLY | ISREGEN,
        "str": 10,
        "exp": 2000,
        "lvl": 13,
        "arm": 2,
        "hpt": 1,
        "dmg": "4x3/3x5",
    },  # extern.c:201
    {
        "ch": "H",
        "name": "hobgoblin",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 3,
        "lvl": 1,
        "arm": 5,
        "hpt": 1,
        "dmg": "1x8",
    },  # extern.c:202
    {
        "ch": "I",
        "name": "ice monster",
        "carry": 0,
        "flags": 0,
        "str": 10,
        "exp": 5,
        "lvl": 1,
        "arm": 9,
        "hpt": 1,
        "dmg": "0x0",
    },  # extern.c:203
    {
        "ch": "J",
        "name": "jabberwock",
        "carry": 70,
        "flags": 0,
        "str": 10,
        "exp": 3000,
        "lvl": 15,
        "arm": 6,
        "hpt": 1,
        "dmg": "2x12/2x4",
    },  # extern.c:204
    {
        "ch": "K",
        "name": "kestrel",
        "carry": 0,
        "flags": ISMEAN | ISFLY,
        "str": 10,
        "exp": 1,
        "lvl": 1,
        "arm": 7,
        "hpt": 1,
        "dmg": "1x4",
    },  # extern.c:205
    {
        "ch": "L",
        "name": "leprechaun",
        "carry": 0,
        "flags": 0,
        "str": 10,
        "exp": 10,
        "lvl": 3,
        "arm": 8,
        "hpt": 1,
        "dmg": "1x1",
    },  # extern.c:206
    {
        "ch": "M",
        "name": "medusa",
        "carry": 40,
        "flags": ISMEAN,
        "str": 10,
        "exp": 200,
        "lvl": 8,
        "arm": 2,
        "hpt": 1,
        "dmg": "3x4/3x4/2x5",
    },  # extern.c:207
    {
        "ch": "N",
        "name": "nymph",
        "carry": 100,
        "flags": 0,
        "str": 10,
        "exp": 37,
        "lvl": 3,
        "arm": 9,
        "hpt": 1,
        "dmg": "0x0",
    },  # extern.c:208
    {
        "ch": "O",
        "name": "orc",
        "carry": 15,
        "flags": ISGREED,
        "str": 10,
        "exp": 5,
        "lvl": 1,
        "arm": 6,
        "hpt": 1,
        "dmg": "1x8",
    },  # extern.c:209
    {
        "ch": "P",
        "name": "phantom",
        "carry": 0,
        "flags": ISINVIS,
        "str": 10,
        "exp": 120,
        "lvl": 8,
        "arm": 3,
        "hpt": 1,
        "dmg": "4x4",
    },  # extern.c:210
    {
        "ch": "Q",
        "name": "quagga",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 15,
        "lvl": 3,
        "arm": 3,
        "hpt": 1,
        "dmg": "1x5/1x5",
    },  # extern.c:211
    {
        "ch": "R",
        "name": "rattlesnake",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 9,
        "lvl": 2,
        "arm": 3,
        "hpt": 1,
        "dmg": "1x6",
    },  # extern.c:212
    {
        "ch": "S",
        "name": "snake",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 2,
        "lvl": 1,
        "arm": 5,
        "hpt": 1,
        "dmg": "1x3",
    },  # extern.c:213
    {
        "ch": "T",
        "name": "troll",
        "carry": 50,
        "flags": ISREGEN | ISMEAN,
        "str": 10,
        "exp": 120,
        "lvl": 6,
        "arm": 4,
        "hpt": 1,
        "dmg": "1x8/1x8/2x6",
    },  # extern.c:214
    {
        "ch": "U",
        "name": "black unicorn",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 190,
        "lvl": 7,
        "arm": -2,
        "hpt": 1,
        "dmg": "1x9/1x9/2x9",
    },  # extern.c:215
    {
        "ch": "V",
        "name": "vampire",
        "carry": 20,
        "flags": ISREGEN | ISMEAN,
        "str": 10,
        "exp": 350,
        "lvl": 8,
        "arm": 1,
        "hpt": 1,
        "dmg": "1x10",
    },  # extern.c:216
    {
        "ch": "W",
        "name": "wraith",
        "carry": 0,
        "flags": 0,
        "str": 10,
        "exp": 55,
        "lvl": 5,
        "arm": 4,
        "hpt": 1,
        "dmg": "1x6",
    },  # extern.c:217
    {
        "ch": "X",
        "name": "xeroc",
        "carry": 30,
        "flags": 0,
        "str": 10,
        "exp": 100,
        "lvl": 7,
        "arm": 7,
        "hpt": 1,
        "dmg": "4x4",
    },  # extern.c:218
    {
        "ch": "Y",
        "name": "yeti",
        "carry": 30,
        "flags": 0,
        "str": 10,
        "exp": 50,
        "lvl": 4,
        "arm": 6,
        "hpt": 1,
        "dmg": "1x6/1x6",
    },  # extern.c:219
    {
        "ch": "Z",
        "name": "zombie",
        "carry": 0,
        "flags": ISMEAN,
        "str": 10,
        "exp": 6,
        "lvl": 2,
        "arm": 8,
        "hpt": 1,
        "dmg": "1x8",
    },  # extern.c:220
]

# ---------------------------------------------------------------------------
# Level-appropriate monster selection.  In 5.4.5 these are `static const int`
# arrays of 26 character codes, not C strings; wand_mons uses the integer 0
# where lvl_mons has a letter, and randmonster() re-rolls while mons[d] == 0
# (monsters.c:50).  Transcribed here as 26-character strings with those zero
# slots written as a space, so index d maps to the same slot and a space means
# "re-roll".  Letters and their positions are character-for-character from C.
# ---------------------------------------------------------------------------

LVL_MONS = "KEBSHIROZLCQANYFTWPXUMVGJD"   # monsters.c:21-24
WAND_MONS = "KEBSH ROZ CQA Y TWP UMVGJ "  # monsters.c:26-29


# Mechanical transcription of the Rogue 5.4.5 magic-item data tables.
# Source tree: build/reference/rogue5.4
# Every value below is copied verbatim from the C; nothing here is designed.
# Pure data: no imports, no functions, no logic.

# ---------------------------------------------------------------------------
# 1. Object type / map characters                                  # rogue.h:88
# ---------------------------------------------------------------------------
PASSAGE = '#'                                                      # rogue.h:90
DOOR = '+'                                                         # rogue.h:91
FLOOR = '.'                                                        # rogue.h:92
PLAYER = '@'                                                       # rogue.h:93
TRAP = '^'                                                         # rogue.h:94
STAIRS = '%'                                                       # rogue.h:95
GOLD = '*'                                                         # rogue.h:96
POTION = '!'                                                       # rogue.h:97
SCROLL = '?'                                                       # rogue.h:98
MAGIC = '$'                                                        # rogue.h:99
FOOD = ':'                                                         # rogue.h:100
WEAPON = ')'                                                       # rogue.h:101
ARMOR = ']'                                                        # rogue.h:102
AMULET = ','                                                       # rogue.h:103
RING = '='                                                         # rogue.h:104
STICK = '/'                                                        # rogue.h:105
CALLABLE = -1                                                      # rogue.h:106
R_OR_S = -2                                                        # rogue.h:107

# Wall characters have NO #define in rogue 5.4.5 -- they are written as bare
# character literals when a room is drawn.
VWALL = '|'                                                        # rooms.c:186
HWALL = '-'                                                        # rooms.c:200

# ---------------------------------------------------------------------------
# 2a. Potion index constants                                      # rogue.h:207
# ---------------------------------------------------------------------------
P_CONFUSE = 0                                                      # rogue.h:209
P_LSD = 1                                                          # rogue.h:210
P_POISON = 2                                                       # rogue.h:211
P_STRENGTH = 3                                                     # rogue.h:212
P_SEEINVIS = 4                                                     # rogue.h:213
P_HEALING = 5                                                      # rogue.h:214
P_MFIND = 6                                                        # rogue.h:215
P_TFIND = 7                                                        # rogue.h:216
P_RAISE = 8                                                        # rogue.h:217
P_XHEAL = 9                                                        # rogue.h:218
P_HASTE = 10                                                       # rogue.h:219
P_RESTORE = 11                                                     # rogue.h:220
P_BLIND = 12                                                       # rogue.h:221
P_LEVIT = 13                                                       # rogue.h:222
MAXPOTIONS = 14                                                    # rogue.h:223

# ---------------------------------------------------------------------------
# 2b. Scroll index constants                                      # rogue.h:226
# ---------------------------------------------------------------------------
S_CONFUSE = 0                                                      # rogue.h:228
S_MAP = 1                                                          # rogue.h:229
S_HOLD = 2                                                         # rogue.h:230
S_SLEEP = 3                                                        # rogue.h:231
S_ARMOR = 4                                                        # rogue.h:232
S_ID_POTION = 5                                                    # rogue.h:233
S_ID_SCROLL = 6                                                    # rogue.h:234
S_ID_WEAPON = 7                                                    # rogue.h:235
S_ID_ARMOR = 8                                                     # rogue.h:236
S_ID_R_OR_S = 9                                                    # rogue.h:237
S_SCARE = 10                                                       # rogue.h:238
S_FDET = 11                                                        # rogue.h:239
S_TELEP = 12                                                       # rogue.h:240
S_ENCH = 13                                                        # rogue.h:241
S_CREATE = 14                                                      # rogue.h:242
S_REMOVE = 15                                                      # rogue.h:243
S_AGGR = 16                                                        # rogue.h:244
S_PROTECT = 17                                                     # rogue.h:245
MAXSCROLLS = 18                                                    # rogue.h:246

# ---------------------------------------------------------------------------
# 2c. Ring index constants                                        # rogue.h:277
# ---------------------------------------------------------------------------
R_PROTECT = 0                                                      # rogue.h:279
R_ADDSTR = 1                                                       # rogue.h:280
R_SUSTSTR = 2                                                      # rogue.h:281
R_SEARCH = 3                                                       # rogue.h:282
R_SEEINVIS = 4                                                     # rogue.h:283
R_NOP = 5                                                          # rogue.h:284
R_AGGR = 6                                                         # rogue.h:285
R_ADDHIT = 7                                                       # rogue.h:286
R_ADDDAM = 8                                                       # rogue.h:287
R_REGEN = 9                                                        # rogue.h:288
R_DIGEST = 10                                                      # rogue.h:289
R_TELEPORT = 11                                                    # rogue.h:290
R_STEALTH = 12                                                     # rogue.h:291
R_SUSTARM = 13                                                     # rogue.h:292
MAXRINGS = 14                                                      # rogue.h:293

# ---------------------------------------------------------------------------
# 2d. Rod / Wand / Staff index constants                          # rogue.h:296
# ---------------------------------------------------------------------------
WS_LIGHT = 0                                                       # rogue.h:298
WS_INVIS = 1                                                       # rogue.h:299
WS_ELECT = 2                                                       # rogue.h:300
WS_FIRE = 3                                                        # rogue.h:301
WS_COLD = 4                                                        # rogue.h:302
WS_POLYMORPH = 5                                                   # rogue.h:303
WS_MISSILE = 6                                                     # rogue.h:304
WS_HASTE_M = 7                                                     # rogue.h:305
WS_SLOW_M = 8                                                      # rogue.h:306
WS_DRAIN = 9                                                       # rogue.h:307
WS_NOP = 10                                                        # rogue.h:308
WS_TELAWAY = 11                                                    # rogue.h:309
WS_TELTO = 12                                                      # rogue.h:310
WS_CANCEL = 13                                                     # rogue.h:311
MAXSTICKS = 14                                                     # rogue.h:312

# ---------------------------------------------------------------------------
# 3. Master item-class probability table
#    C: struct obj_info things[NUMTHINGS]  -- extern.c:225
#    The C initializer stores oi_name as 0 (NULL) for every row; the object
#    TYPE comes from the row INDEX via the switch in things.c:236 new_thing():
#      0 POTION, 1 SCROLL, 2 FOOD, 3 WEAPON, 4 ARMOR, 5 RING, 6 STICK.
#    The "name" strings below are the trailing C comments on each row.
#    Raw probabilities; sum == 100.  init_probs()/sumprobs() (init.c:410,384)
#    converts these to running cumulative totals at startup.
# ---------------------------------------------------------------------------
THINGS = [
    {"type": POTION, "prob": 26, "name": "potion"},                # extern.c:226
    {"type": SCROLL, "prob": 36, "name": "scroll"},                # extern.c:227
    {"type": FOOD,   "prob": 16, "name": "food"},                  # extern.c:228
    {"type": WEAPON, "prob":  7, "name": "weapon"},                # extern.c:229
    {"type": ARMOR,  "prob":  7, "name": "armor"},                 # extern.c:230
    {"type": RING,   "prob":  4, "name": "ring"},                  # extern.c:231
    {"type": STICK,  "prob":  4, "name": "stick"},                 # extern.c:232
]                                                                  # extern.c:233

# ---------------------------------------------------------------------------
# 4a. Potions -- struct obj_info pot_info[MAXPOTIONS]              # extern.c:245
#     Order is identity: index == P_* constant.  probs sum to 100.
# ---------------------------------------------------------------------------
POT_INFO = [
    {"name": "confusion",         "prob":  7, "worth":   5, "guess": None, "know": False},  # extern.c:246 P_CONFUSE
    {"name": "hallucination",     "prob":  8, "worth":   5, "guess": None, "know": False},  # extern.c:247 P_LSD
    {"name": "poison",            "prob":  8, "worth":   5, "guess": None, "know": False},  # extern.c:248 P_POISON
    {"name": "gain strength",     "prob": 13, "worth": 150, "guess": None, "know": False},  # extern.c:249 P_STRENGTH
    {"name": "see invisible",     "prob":  3, "worth": 100, "guess": None, "know": False},  # extern.c:250 P_SEEINVIS
    {"name": "healing",           "prob": 13, "worth": 130, "guess": None, "know": False},  # extern.c:251 P_HEALING
    {"name": "monster detection", "prob":  6, "worth": 130, "guess": None, "know": False},  # extern.c:252 P_MFIND
    {"name": "magic detection",   "prob":  6, "worth": 105, "guess": None, "know": False},  # extern.c:253 P_TFIND
    {"name": "raise level",       "prob":  2, "worth": 250, "guess": None, "know": False},  # extern.c:254 P_RAISE
    {"name": "extra healing",     "prob":  5, "worth": 200, "guess": None, "know": False},  # extern.c:255 P_XHEAL
    {"name": "haste self",        "prob":  5, "worth": 190, "guess": None, "know": False},  # extern.c:256 P_HASTE
    {"name": "restore strength",  "prob": 13, "worth": 130, "guess": None, "know": False},  # extern.c:257 P_RESTORE
    {"name": "blindness",         "prob":  5, "worth":   5, "guess": None, "know": False},  # extern.c:258 P_BLIND
    {"name": "levitation",        "prob":  6, "worth":  75, "guess": None, "know": False},  # extern.c:259 P_LEVIT
]                                                                  # extern.c:260

# ---------------------------------------------------------------------------
# 4b. Scrolls -- struct obj_info scr_info[MAXSCROLLS]              # extern.c:277
#     Order is identity: index == S_* constant.  probs sum to 100.
# ---------------------------------------------------------------------------
SCR_INFO = [
    {"name": "monster confusion",           "prob":  7, "worth": 140, "guess": None, "know": False},  # extern.c:278 S_CONFUSE
    {"name": "magic mapping",               "prob":  4, "worth": 150, "guess": None, "know": False},  # extern.c:279 S_MAP
    {"name": "hold monster",                "prob":  2, "worth": 180, "guess": None, "know": False},  # extern.c:280 S_HOLD
    {"name": "sleep",                       "prob":  3, "worth":   5, "guess": None, "know": False},  # extern.c:281 S_SLEEP
    {"name": "enchant armor",               "prob":  7, "worth": 160, "guess": None, "know": False},  # extern.c:282 S_ARMOR
    {"name": "identify potion",             "prob": 10, "worth":  80, "guess": None, "know": False},  # extern.c:283 S_ID_POTION
    {"name": "identify scroll",             "prob": 10, "worth":  80, "guess": None, "know": False},  # extern.c:284 S_ID_SCROLL
    {"name": "identify weapon",             "prob":  6, "worth":  80, "guess": None, "know": False},  # extern.c:285 S_ID_WEAPON
    {"name": "identify armor",              "prob":  7, "worth": 100, "guess": None, "know": False},  # extern.c:286 S_ID_ARMOR
    {"name": "identify ring, wand or staff","prob": 10, "worth": 115, "guess": None, "know": False},  # extern.c:287 S_ID_R_OR_S
    {"name": "scare monster",               "prob":  3, "worth": 200, "guess": None, "know": False},  # extern.c:288 S_SCARE
    {"name": "food detection",              "prob":  2, "worth":  60, "guess": None, "know": False},  # extern.c:289 S_FDET
    {"name": "teleportation",               "prob":  5, "worth": 165, "guess": None, "know": False},  # extern.c:290 S_TELEP
    {"name": "enchant weapon",              "prob":  8, "worth": 150, "guess": None, "know": False},  # extern.c:291 S_ENCH
    {"name": "create monster",              "prob":  4, "worth":  75, "guess": None, "know": False},  # extern.c:292 S_CREATE
    {"name": "remove curse",                "prob":  7, "worth": 105, "guess": None, "know": False},  # extern.c:293 S_REMOVE
    {"name": "aggravate monsters",          "prob":  3, "worth":  20, "guess": None, "know": False},  # extern.c:294 S_AGGR
    {"name": "protect armor",               "prob":  2, "worth": 250, "guess": None, "know": False},  # extern.c:295 S_PROTECT
]                                                                  # extern.c:296

# ---------------------------------------------------------------------------
# 4c. Rings -- struct obj_info ring_info[MAXRINGS]                 # extern.c:261
#     Order is identity: index == R_* constant.  probs sum to 100.
#     NOTE: at startup init_stones() (init.c:298) ADDS the value of the
#     randomly-assigned stone to oi_worth, so the runtime worth is
#     worth + STONES[j]["value"].  The numbers below are the base initializer.
# ---------------------------------------------------------------------------
RING_INFO = [
    {"name": "protection",        "prob":  9, "worth": 400, "guess": None, "know": False},  # extern.c:262 R_PROTECT
    {"name": "add strength",      "prob":  9, "worth": 400, "guess": None, "know": False},  # extern.c:263 R_ADDSTR
    {"name": "sustain strength",  "prob":  5, "worth": 280, "guess": None, "know": False},  # extern.c:264 R_SUSTSTR
    {"name": "searching",         "prob": 10, "worth": 420, "guess": None, "know": False},  # extern.c:265 R_SEARCH
    {"name": "see invisible",     "prob": 10, "worth": 310, "guess": None, "know": False},  # extern.c:266 R_SEEINVIS
    {"name": "adornment",         "prob":  1, "worth":  10, "guess": None, "know": False},  # extern.c:267 R_NOP
    {"name": "aggravate monster", "prob": 10, "worth":  10, "guess": None, "know": False},  # extern.c:268 R_AGGR
    {"name": "dexterity",         "prob":  8, "worth": 440, "guess": None, "know": False},  # extern.c:269 R_ADDHIT
    {"name": "increase damage",   "prob":  8, "worth": 400, "guess": None, "know": False},  # extern.c:270 R_ADDDAM
    {"name": "regeneration",      "prob":  4, "worth": 460, "guess": None, "know": False},  # extern.c:271 R_REGEN
    {"name": "slow digestion",    "prob":  9, "worth": 240, "guess": None, "know": False},  # extern.c:272 R_DIGEST
    {"name": "teleportation",     "prob":  5, "worth":  30, "guess": None, "know": False},  # extern.c:273 R_TELEPORT
    {"name": "stealth",           "prob":  7, "worth": 470, "guess": None, "know": False},  # extern.c:274 R_STEALTH
    {"name": "maintain armor",    "prob":  5, "worth": 380, "guess": None, "know": False},  # extern.c:275 R_SUSTARM
]                                                                  # extern.c:276

# ---------------------------------------------------------------------------
# 4d. Rods/Wands/Staves -- struct obj_info ws_info[MAXSTICKS]      # extern.c:309
#     Order is identity: index == WS_* constant.  probs sum to 100.
# ---------------------------------------------------------------------------
WS_INFO = [
    {"name": "light",          "prob": 12, "worth": 250, "guess": None, "know": False},  # extern.c:310 WS_LIGHT
    {"name": "invisibility",   "prob":  6, "worth":   5, "guess": None, "know": False},  # extern.c:311 WS_INVIS
    {"name": "lightning",      "prob":  3, "worth": 330, "guess": None, "know": False},  # extern.c:312 WS_ELECT
    {"name": "fire",           "prob":  3, "worth": 330, "guess": None, "know": False},  # extern.c:313 WS_FIRE
    {"name": "cold",           "prob":  3, "worth": 330, "guess": None, "know": False},  # extern.c:314 WS_COLD
    {"name": "polymorph",      "prob": 15, "worth": 310, "guess": None, "know": False},  # extern.c:315 WS_POLYMORPH
    {"name": "magic missile",  "prob": 10, "worth": 170, "guess": None, "know": False},  # extern.c:316 WS_MISSILE
    {"name": "haste monster",  "prob": 10, "worth":   5, "guess": None, "know": False},  # extern.c:317 WS_HASTE_M
    {"name": "slow monster",   "prob": 11, "worth": 350, "guess": None, "know": False},  # extern.c:318 WS_SLOW_M
    {"name": "drain life",     "prob":  9, "worth": 300, "guess": None, "know": False},  # extern.c:319 WS_DRAIN
    {"name": "nothing",        "prob":  1, "worth":   5, "guess": None, "know": False},  # extern.c:320 WS_NOP
    {"name": "teleport away",  "prob":  6, "worth": 340, "guess": None, "know": False},  # extern.c:321 WS_TELAWAY
    {"name": "teleport to",    "prob":  6, "worth":  50, "guess": None, "know": False},  # extern.c:322 WS_TELTO
    {"name": "cancellation",   "prob":  5, "worth": 280, "guess": None, "know": False},  # extern.c:323 WS_CANCEL
]                                                                  # extern.c:324

# ---------------------------------------------------------------------------
# 5a. RAINBOW -- potion colors, const char *rainbow[]  (27 entries)  # init.c:81
# ---------------------------------------------------------------------------
RAINBOW = [
    "amber",
    "aquamarine",
    "black",
    "blue",
    "brown",
    "clear",
    "crimson",
    "cyan",
    "ecru",
    "gold",
    "green",
    "grey",
    "magenta",
    "orange",
    "pink",
    "plaid",
    "purple",
    "red",
    "silver",
    "tan",
    "tangerine",
    "topaz",
    "turquoise",
    "vermilion",
    "violet",
    "white",
    "yellow",
]                                                                  # init.c:109

# ---------------------------------------------------------------------------
# 5b. STONES -- ring stone settings, const STONE stones[]  (26 entries)
#     struct STONE { char *st_name; int st_value; }               # rogue.h:469
#     The C pairs name with value, so this is emitted as dicts.   # init.c:132
#     NOTE: the list is NOT strictly alphabetical -- "garnet" follows
#     "granite", and "taaffeite" follows "turquoise", exactly as in the C.
# ---------------------------------------------------------------------------
STONES = [
    {"name": "agate",          "value":  25},                      # init.c:133
    {"name": "alexandrite",    "value":  40},                      # init.c:134
    {"name": "amethyst",       "value":  50},                      # init.c:135
    {"name": "carnelian",      "value":  40},                      # init.c:136
    {"name": "diamond",        "value": 300},                      # init.c:137
    {"name": "emerald",        "value": 300},                      # init.c:138
    {"name": "germanium",      "value": 225},                      # init.c:139
    {"name": "granite",        "value":   5},                      # init.c:140
    {"name": "garnet",         "value":  50},                      # init.c:141
    {"name": "jade",           "value": 150},                      # init.c:142
    {"name": "kryptonite",     "value": 300},                      # init.c:143
    {"name": "lapis lazuli",   "value":  50},                      # init.c:144
    {"name": "moonstone",      "value":  50},                      # init.c:145
    {"name": "obsidian",       "value":  15},                      # init.c:146
    {"name": "onyx",           "value":  60},                      # init.c:147
    {"name": "opal",           "value": 200},                      # init.c:148
    {"name": "pearl",          "value": 220},                      # init.c:149
    {"name": "peridot",        "value":  63},                      # init.c:150
    {"name": "ruby",           "value": 350},                      # init.c:151
    {"name": "sapphire",       "value": 285},                      # init.c:152
    {"name": "stibotantalite", "value": 200},                      # init.c:153
    {"name": "tiger eye",      "value":  50},                      # init.c:154
    {"name": "topaz",          "value":  60},                      # init.c:155
    {"name": "turquoise",      "value":  70},                      # init.c:156
    {"name": "taaffeite",      "value": 300},                      # init.c:157
    {"name": "zircon",         "value":  80},                      # init.c:158
]                                                                  # init.c:159

# ---------------------------------------------------------------------------
# 5c. WOOD -- staff materials, const char *wood[]  (33 entries)    # init.c:163
# ---------------------------------------------------------------------------
WOOD = [
    "avocado wood",
    "balsa",
    "bamboo",
    "banyan",
    "birch",
    "cedar",
    "cherry",
    "cinnibar",
    "cypress",
    "dogwood",
    "driftwood",
    "ebony",
    "elm",
    "eucalyptus",
    "fall",
    "hemlock",
    "holly",
    "ironwood",
    "kukui wood",
    "mahogany",
    "manzanita",
    "maple",
    "oaken",
    "persimmon wood",
    "pecan",
    "pine",
    "poplar",
    "redwood",
    "rosewood",
    "spruce",
    "teak",
    "walnut",
    "zebrawood",
]                                                                  # init.c:197

# ---------------------------------------------------------------------------
# 5d. METAL -- wand materials, const char *metal[]  (22 entries)   # init.c:201
# ---------------------------------------------------------------------------
METAL = [
    "aluminum",
    "beryllium",
    "bone",
    "brass",
    "bronze",
    "copper",
    "electrum",
    "gold",
    "iron",
    "lead",
    "magnesium",
    "mercury",
    "nickel",
    "pewter",
    "platinum",
    "steel",
    "silver",
    "silicon",
    "tin",
    "titanium",
    "tungsten",
    "zinc",
]                                                                  # init.c:224

# ---------------------------------------------------------------------------
# 5e. SYLLABLES -- scroll-title syllables, static const char *sylls[]
#     (147 entries).  NOTE: "nes" appears TWICE (init.c:121) -- that
#     duplicate is in the original C and is preserved here.        # init.c:113
# ---------------------------------------------------------------------------
SYLLABLES = [
    "a", "ab", "ag", "aks", "ala", "an", "app", "arg", "arze", "ash",
    "bek", "bie", "bit", "bjor", "blu", "bot", "bu", "byt", "comp",
    "con", "cos", "cre", "dalf", "dan", "den", "do", "e", "eep", "el",
    "eng", "er", "ere", "erk", "esh", "evs", "fa", "fid", "fri", "fu",
    "gan", "gar", "glen", "gop", "gre", "ha", "hyd", "i", "ing", "ip",
    "ish", "it", "ite", "iv", "jo", "kho", "kli", "klis", "la", "lech",
    "mar", "me", "mi", "mic", "mik", "mon", "mung", "mur", "nej",
    "nelg", "nep", "ner", "nes", "nes", "nih", "nin", "o", "od", "ood",
    "org", "orn", "ox", "oxy", "pay", "ple", "plu", "po", "pot",
    "prok", "re", "rea", "rhov", "ri", "ro", "rog", "rok", "rol", "sa",
    "san", "sat", "sef", "seh", "shu", "ski", "sna", "sne", "snik",
    "sno", "so", "sol", "sri", "sta", "sun", "ta", "tab", "tem",
    "ther", "ti", "tox", "trol", "tue", "turs", "u", "ulk", "um", "un",
    "uni", "ur", "val", "viv", "vly", "vom", "wah", "wed", "werg",
    "wex", "whon", "wun", "xo", "y", "yot", "yu", "zant", "zeb", "zim",
    "zok", "zon", "zum",
]                                                                  # init.c:130

# ---------------------------------------------------------------------------
# 6. Item-related limits                                          # rogue.h:24
#    NOTE: rogue 5.4.5 has NO MAXENCHANT define anywhere in the tree.
# ---------------------------------------------------------------------------
MAXROOMS = 9                                                       # rogue.h:26
MAXTHINGS = 9                                                      # rogue.h:27
MAXOBJ = 9                                                         # rogue.h:28
MAXPACK = 23                                                       # rogue.h:29
MAXTRAPS = 10                                                      # rogue.h:30
AMULETLEVEL = 26                                                   # rogue.h:31
NUMTHINGS = 7                                                      # rogue.h:32
MAXPASS = 13                                                       # rogue.h:33
BORE_LEVEL = 50                                                    # rogue.h:37
MAXWEAPONS = 9                                                     # rogue.h:261
MAXARMORS = 8                                                      # rogue.h:274
MAXSTR = 1024                                                      # extern.h:111
MAXNAME = 40                                                       # init.c:259


# tables_combat.py
#
# MECHANICAL TRANSCRIPTION of the combat-related data tables of authentic
# Rogue 5.4.5 (Toy / Arnold / Wichman, BSD sources).  Pure data: no imports,
# no functions, no logic.  Every value below is copied field-for-field from
# the C.  Each table carries a "# <file>:<line>" reference to the exact
# source location it came from.
#
# DICE NOTATION WARNING: Rogue 5.4 writes dice as "NxM", not "NdM".  See
# fight.c:457-479 (roll_em) -- it does atoi(cp), then strchr(cp, 'x'), then
# atoi(++cp), and splits multiple attacks on '/'.  The damage strings below
# are reproduced EXACTLY as they appear in the C, so they use 'x'.
# "2x4" means 2d4.  '/' separates multiple attacks in one round.


# ---------------------------------------------------------------------------
# 1. Weapon index constants
# ---------------------------------------------------------------------------
MACE = 0
SWORD = 1
BOW = 2
ARROW = 3
DAGGER = 4
TWOSWORD = 5
DART = 6
SHIRAKEN = 7
SPEAR = 8
FLAME = 9          # fake entry for dragon breath (ick)
MAXWEAPONS = 9     # this should equal FLAME
# rogue.h:251

NO_WEAPON = -1
# weapons.c:17   -- #define NO_WEAPON -1  (value of iw_launch for "no launcher")

# Armor index constants
LEATHER = 0
RING_MAIL = 1
STUDDED_LEATHER = 2
SCALE_MAIL = 3
CHAIN_MAIL = 4
SPLINT_MAIL = 5
BANDED_MAIL = 6
PLATE_MAIL = 7
MAXARMORS = 8
# rogue.h:266

# Object flag bits (octal in the C) -- needed to read the WEAPONS "flags" field
ISCURSED = 0o000001   # object is cursed
ISKNOW = 0o000002     # player knows details about the object
ISMISL = 0o000004     # object is a missile type
ISMANY = 0o000010     # object comes in groups
ISPROT = 0o000040     # armor is permanently protected
# rogue.h:154


# ---------------------------------------------------------------------------
# 2. WEAPONS
# ---------------------------------------------------------------------------
# Merge of two C tables, both in index order MACE..SPEAR:
#
#   struct init_weaps { char *iw_dam; char *iw_hrl; int iw_launch; int iw_flags; }
#       init_dam[MAXWEAPONS]                      weapons.c:20 / weapons.c:25
#   struct obj_info   { const char *oi_name; int oi_prob; int oi_worth;
#                       char *oi_guess; int oi_know; }
#       weap_info[MAXWEAPONS + 1]                 extern.c:297
#
# oi_guess (NULL) and oi_know (FALSE) are per-game runtime identification
# state, not static data, so they are not reproduced here.
#
# The oi_prob values as written are INDEPENDENT percentages summing to 100.
# init_probs() -> sumprobs() (init.c:383) converts them IN PLACE to a running
# cumulative total at startup; pick_one() then rolls rnd(100) against the
# cumulative array.  The raw (non-cumulative) values are given below.
#
# NOTE on the dagger: the C literally reads "ISMISL|ISMISL" -- ISMISL OR'd
# with itself.  That is a typo in the original source (5.4.5 ships it), and
# it evaluates to plain ISMISL == 4.  Transcribed as the value the C
# actually produces: 4.
#
# NOTE: index 7's constant is spelled SHIRAKEN in rogue.h but its oi_name is
# "shuriken".  Both spellings are reproduced as they appear.
#
# The 10th weap_info entry, { NULL, 0 }, is the FLAME slot -- a placeholder
# for dragon's breath whose oi_name is overwritten at runtime by
# sticks.c:315.  It is not a real weapon, has no init_dam row, and is
# excluded from MAXWEAPONS/pick_one, so it is not listed here.

WEAPONS = [
    {"name": "mace",             "dmg": "2x4", "hurl_dmg": "1x3", "launch": None, "flags": 0,  "worth": 8,   "prob": 11},
    {"name": "long sword",       "dmg": "3x4", "hurl_dmg": "1x2", "launch": None, "flags": 0,  "worth": 15,  "prob": 11},
    {"name": "short bow",        "dmg": "1x1", "hurl_dmg": "1x1", "launch": None, "flags": 0,  "worth": 15,  "prob": 12},
    {"name": "arrow",            "dmg": "1x1", "hurl_dmg": "2x3", "launch": BOW,  "flags": 12, "worth": 1,   "prob": 12},  # ISMANY|ISMISL
    {"name": "dagger",           "dmg": "1x6", "hurl_dmg": "1x4", "launch": None, "flags": 4,  "worth": 3,   "prob": 8},   # ISMISL|ISMISL (C typo) == ISMISL
    {"name": "two handed sword", "dmg": "4x4", "hurl_dmg": "1x2", "launch": None, "flags": 0,  "worth": 75,  "prob": 10},
    {"name": "dart",             "dmg": "1x1", "hurl_dmg": "1x3", "launch": None, "flags": 12, "worth": 2,   "prob": 12},  # ISMANY|ISMISL
    {"name": "shuriken",         "dmg": "1x2", "hurl_dmg": "2x4", "launch": None, "flags": 12, "worth": 5,   "prob": 12},  # ISMANY|ISMISL
    {"name": "spear",            "dmg": "2x3", "hurl_dmg": "1x6", "launch": None, "flags": 4,  "worth": 5,   "prob": 12},  # ISMISL
]
# weapons.c:25 (init_dam) + extern.c:297 (weap_info)
# prob sum = 11+11+12+12+8+10+12+12+12 = 100

# Stack counts set by init_weapon() (weapons.c:157):
#   DAGGER          -> o_count = rnd(4) + 2   (2..5),   new o_group
#   flags & ISMANY  -> o_count = rnd(8) + 8   (8..15),  new o_group
#   otherwise       -> o_count = 1,           o_group = 0
# weapons.c:174


# ---------------------------------------------------------------------------
# 3. ARMORS
# ---------------------------------------------------------------------------
# struct obj_info arm_info[MAXARMORS]      extern.c:235   (oi_name, oi_prob, oi_worth)
# const int a_class[MAXARMORS]             extern.c:101   (base armor class)
#
# As with weapons, oi_prob values are raw independent percentages summing to
# 100; sumprobs() makes them cumulative at startup.
#
# "ac" is the a_class[] base value: LOWER IS BETTER (AD&D descending AC).
# things.c:260 rolls the actual item as
#   cur->o_arm = a_class[cur->o_which];
#   if ((r = rnd(100)) < 20) { cur->o_flags |= ISCURSED; cur->o_arm += rnd(3)+1; }
#   else if (r < 28)         {                           cur->o_arm -= rnd(3)+1; }
# -- one roll: 20% cursed/worse, 8% blessed/better, 72% plain.

ARMORS = [
    {"name": "leather armor",          "prob": 20, "worth": 20,  "ac": 8},
    {"name": "ring mail",              "prob": 15, "worth": 25,  "ac": 7},
    {"name": "studded leather armor",  "prob": 15, "worth": 20,  "ac": 7},
    {"name": "scale mail",             "prob": 13, "worth": 30,  "ac": 6},
    {"name": "chain mail",             "prob": 12, "worth": 75,  "ac": 5},
    {"name": "splint mail",            "prob": 10, "worth": 80,  "ac": 4},
    {"name": "banded mail",            "prob": 10, "worth": 90,  "ac": 4},
    {"name": "plate mail",             "prob": 5,  "worth": 150, "ac": 3},
]
# extern.c:235 (arm_info) + extern.c:101 (a_class)
# prob sum = 20+15+15+13+12+10+10+5 = 100
# The player starts in RING_MAIL with o_arm = a_class[RING_MAIL] - 1 == 6
# (init.c:42).


# ---------------------------------------------------------------------------
# 4. E_LEVELS  -- experience-point thresholds
# ---------------------------------------------------------------------------
# The table lives in extern.c:124 as `const int e_levels[]`, NOT in init.c.
# (init.c only contains init_player/init_probs/etc.)  It is written in the C
# with `L` long suffixes; the values are unchanged.
#
# 20 real threshold entries, PLUS a 21st entry of 0L that acts as the
# end-of-table sentinel.  E_LEVELS below holds only the 20 real thresholds;
# the trailing 0 terminator is a loop guard, not a threshold.
#
# WHAT THE C DOES PAST THE END OF THE TABLE -- misc.c:322 check_level():
#
#     for (i = 0; e_levels[i] != 0; i++)
#         if (e_levels[i] > pstats.s_exp)
#             break;
#     i++;
#     olevel = pstats.s_lvl;
#     pstats.s_lvl = i;
#     if (i > olevel)
#     {
#         add = roll(i - olevel, 10);
#         max_hp += add;
#         pstats.s_hpt += add;
#         msg("welcome to level %d", i);
#     }
#
# The rule, stated precisely:
#   * Scan forward for the first entry STRICTLY GREATER than current exp.
#   * The loop ALSO terminates on the 0 sentinel.
#   * level = (index reached) + 1.
#   * So exp < 10 -> break at i=0 -> level 1.  exp >= 8000000 -> the loop
#     runs off the real entries and stops at the sentinel with i == 20 ->
#     level 21.
#   * THERE IS NO DOUBLING PAST THE END OF THE TABLE IN 5.4.5.  The level
#     hard-caps at 21; further experience gives no further levels and no
#     further hit points.  (The *table itself* roughly doubles as it goes --
#     10, 20, 40, 80, 160, 320, 640, then irregular jumps at 1300 and above --
#     but that doubling is baked into the literal values, not computed.)
#   * On gaining N levels at once, HP gain is roll(N, 10) = N d10, added to
#     both max_hp and current hp.
#   * Level LOSS (wraith drain, fight.c:254) and potion of raise level
#     (potions.c:346) set exp back to e_levels[lvl-1] + 1.

E_LEVELS = [
    10,
    20,
    40,
    80,
    160,
    320,
    640,
    1300,
    2600,
    5200,
    13000,
    26000,
    50000,
    100000,
    200000,
    400000,
    800000,
    2000000,
    4000000,
    8000000,
]
# extern.c:124  -- 20 thresholds; the C array has a 21st entry, 0L, as the
# sentinel.  Max attainable character level is 21.

E_LEVELS_TERMINATOR = 0
MAX_CHAR_LEVEL = 21
# extern.c:124 / misc.c:327


# ---------------------------------------------------------------------------
# 5. Strength bonus tables
# ---------------------------------------------------------------------------
# Original C, verbatim (fight.c:43-57):
#
#     /*
#      * adjustments to hit probabilities due to strength
#      */
#     static int str_plus[] = {
#         -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1,
#         1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3,
#     };
#
#     /*
#      * adjustments to damage done due to strength
#      */
#     static int add_dam[] = {
#         -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3,
#         3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6
#     };
#
# THESE ARE FLAT ARRAYS INDEXED DIRECTLY BY THE RAW STRENGTH VALUE -- there
# is no if-chain, no 18/xx percentile system, and no 3..18 AD&D remapping.
# Rogue 5.4 strength is a plain int.  Usage, fight.c:463 and fight.c:472:
#
#     if (swing(att->s_lvl, def_arm, hplus + str_plus[att->s_str]))
#     {
#         proll = roll(ndice, nsides);
#         damage = dplus + proll + add_dam[att->s_str];
#         def->s_hpt -= max(0, damage);
#         did_hit = TRUE;
#     }
#
# and swing() itself (fight.c:379):
#     int res  = rnd(20);
#     int need = (20 - at_lvl) - op_arm;
#     return (res + wplus >= need);
#
# STRENGTH RANGE: both arrays have exactly 32 entries, covering index 0..31.
# add_str() (misc.c:369) clamps strength to [3, 31]:
#
#     if ((*sp += amt) < 3)   *sp = 3;
#     else if (*sp > 31)      *sp = 31;
#
# so indices 0, 1 and 2 exist in the C arrays but are unreachable for the
# player.  They are transcribed anyway (values -7, -6, -5 in both tables)
# because monsters index the same arrays and the array contents are what the
# C contains.  Monster strength is the macro XX == 10 for every monster
# (extern.c:189), giving them str_plus 0 / add_dam 0.  Player starting
# strength is 16 (INIT_STATS, extern.c:166), giving str_plus 0 / add_dam +1.

# to-hit bonus, keyed by strength (index == strength value)
STR_PLUS = [
    -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1,
    1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3,
]
# fight.c:46  -- 32 entries, index 0..31

# damage bonus, keyed by strength (index == strength value)
ADD_DAM = [
    -7, -6, -5, -4, -3, -2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3,
    3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6,
]
# fight.c:54  -- 32 entries, index 0..31

# Same data as dicts keyed by strength, for the legal player range only.
STR_PLUS_BY_STR = {
    3: -4, 4: -3, 5: -2, 6: -1, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0,
    13: 0, 14: 0, 15: 0, 16: 0, 17: 1, 18: 1, 19: 1, 20: 1, 21: 2, 22: 2,
    23: 2, 24: 2, 25: 2, 26: 2, 27: 2, 28: 2, 29: 2, 30: 2, 31: 3,
}
# fight.c:46  -- STR_PLUS[3..31]

ADD_DAM_BY_STR = {
    3: -4, 4: -3, 5: -2, 6: -1, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0,
    13: 0, 14: 0, 15: 0, 16: 1, 17: 1, 18: 2, 19: 3, 20: 3, 21: 4, 22: 5,
    23: 5, 24: 5, 25: 5, 26: 5, 27: 5, 28: 5, 29: 5, 30: 5, 31: 6,
}
# fight.c:54  -- ADD_DAM[3..31]

STR_MIN = 3
STR_MAX = 31
# misc.c:369 add_str()


# ---------------------------------------------------------------------------
# 6. Timing constants
# ---------------------------------------------------------------------------
# rogue.h:112-124.  BEARTIME/SLEEPTIME/HOLDTIME/WANDERTIME/BEFORE/AFTER are
# macros wrapping spread():
#
#     #define spread(nm)   -> misc.c:535:  return nm - nm / 20 + rnd(nm / 10);
#     #define rnd(range)   -> main.c:190:  return range == 0 ? 0 : abs((int) RN) % range;
#
# For small nm both nm/20 and nm/10 are 0, and rnd(0) == 0, so spread(1) == 1
# and spread(2) == 2 EXACTLY.  BEFORE and AFTER are therefore hard constants
# 1 and 2 -- they are used as the daemon/fuse *type* tag compared for
# equality in do_daemons()/do_fuses(), so they must be.
# Only the larger ones actually randomize.

HUNGERTIME = 1300      # rogue.h:121  -- food_left at game start (init.c:29)
STOMACHSIZE = 2000     # rogue.h:123  -- cap on food_left when eating
MORETIME = 150         # rogue.h:122  -- hunger-state boundary (see below)
STARVETIME = 850       # rogue.h:124  -- turns past 0 food before death('s')
HEALTIME = 30          # rogue.h:118
HUHDURATION = 20       # rogue.h:119
SEEDURATION = 850      # rogue.h:120
BEFORE = 1             # rogue.h:116  -- spread(1), always 1
AFTER = 2              # rogue.h:117  -- spread(2), always 2
BEARTIME = 3           # rogue.h:112  -- spread(3), always 3
SLEEPTIME = 5          # rogue.h:113  -- spread(5), always 5
HOLDTIME = 2           # rogue.h:114  -- spread(2), always 2
WANDERTIME_BASE = 70   # rogue.h:115  -- spread(70) == 70 - 3 + rnd(7) == 67..73
WANDERTIME_MIN = 67
WANDERTIME_MAX = 73
BORE_LEVEL = 50        # rogue.h:37   -- frozen this long by an ice monster == death
AMULETLEVEL = 26       # rogue.h:31

# STARTTIME: NO SUCH CONSTANT EXISTS IN ROGUE 5.4.5.  A full grep of the
# distribution (rogue.h and all .c files) finds no STARTTIME.  The starting
# food clock is HUNGERTIME (init.c:29: food_left = HUNGERTIME).  No value is
# invented for it here.

# Hunger states, daemons.c:139 stomach():
#   food_left -= ring_eat(LEFT) + ring_eat(RIGHT) + 1 - amulet;   (per turn)
#   crossing below 2*MORETIME (300) -> hungry_state = 1 "hungry"
#   crossing below   MORETIME (150) -> hungry_state = 2 "weak"
#   food_left <= 0 and food_left-- < -STARVETIME -> death('s')
#   while food_left <= 0: 1-in-5 chance per turn of fainting,
#       no_command += rnd(8) + 4, hungry_state = 3 "faint"
# Eating (misc.c:298):
#   food_left += HUNGERTIME - 200 + rnd(400)   (i.e. +1100..+1499), capped at
#   STOMACHSIZE.
HUNGRY_STATE_OK = 0
HUNGRY_STATE_HUNGRY = 1     # food_left < 2 * MORETIME  (< 300)
HUNGRY_STATE_WEAK = 2       # food_left < MORETIME      (< 150)
HUNGRY_STATE_FAINT = 3      # food_left <= 0
# daemons.c:139

# --- HP regeneration: doctor(), daemons.c:18 ---
# Original C, verbatim:
#
#     void
#     doctor(void)
#     {
#         int lv, ohp;
#
#         lv = pstats.s_lvl;
#         ohp = pstats.s_hpt;
#         quiet++;
#         if (lv < 8)
#         {
#             if (quiet + (lv << 1) > 20)
#                 pstats.s_hpt++;
#         }
#         else
#             if (quiet >= 3)
#                 pstats.s_hpt += rnd(lv - 7) + 1;
#         if (ISRING(LEFT, R_REGEN))
#             pstats.s_hpt++;
#         if (ISRING(RIGHT, R_REGEN))
#             pstats.s_hpt++;
#         if (ohp != pstats.s_hpt)
#         {
#             if (pstats.s_hpt > max_hp)
#                 pstats.s_hpt = max_hp;
#             quiet = 0;
#         }
#     }
#
# doctor is started as an AFTER daemon at main.c:152 and therefore runs once
# per player turn.  `quiet` is the count of consecutive turns without combat;
# fight()/attack() reset it to 0 (fight.c:86, fight.c:153).
#
# THE RULE, PRECISELY:
#   quiet is incremented FIRST, so every test below is against the
#   post-increment value.
#
#   Levels 1..7:  heal exactly +1 hp when  quiet + 2*lvl > 20,
#                 i.e. when  quiet >= 21 - 2*lvl.
#   Levels 8+:    heal  rnd(lvl - 7) + 1  hp (uniform in 1..lvl-7, since
#                 rnd(n) yields 0..n-1) whenever quiet >= 3.
#                 At lvl 8 that is rnd(1)+1 == exactly 1.
#
#   Each worn ring of regeneration adds a further +1 hp, UNCONDITIONALLY --
#   it is outside both branches, so it fires every single turn regardless of
#   quiet or level (two rings -> +2/turn).
#
#   quiet is reset to 0 ONLY IF hp actually changed this call.  The test
#   `ohp != pstats.s_hpt` is evaluated BEFORE the max_hp clamp, so a heal
#   that gets clamped straight back down to max_hp STILL resets quiet.
#   quiet only fails to reset when no heal branch fired at all.
#
#   Consequence for levels 1..7: because quiet resets on each heal, the
#   steady-state interval between +1 hp ticks is (21 - 2*lvl) turns.

# Turns of quiet required for a +1 hp tick, levels 1..7 (lvl < 8 branch).
# Value is the smallest post-increment `quiet` satisfying quiet + 2*lvl > 20.
REGEN_QUIET_NEEDED = {
    1: 19,
    2: 17,
    3: 15,
    4: 13,
    5: 11,
    6: 9,
    7: 7,
}
# daemons.c:29-32  -- if (lv < 8) { if (quiet + (lv << 1) > 20) pstats.s_hpt++; }

REGEN_LOW_LEVEL_AMOUNT = 1
# daemons.c:31  -- pstats.s_hpt++  (always exactly 1)

REGEN_HIGH_LEVEL_MIN_LEVEL = 8
REGEN_HIGH_LEVEL_QUIET_NEEDED = 3
# daemons.c:34  -- else if (quiet >= 3) pstats.s_hpt += rnd(lv - 7) + 1;

# Heal amount range (inclusive) for levels 8..21 once quiet >= 3.
# amount = rnd(lvl - 7) + 1, uniform over 1 .. (lvl - 7).
REGEN_HIGH_LEVEL_AMOUNT = {
    8:  (1, 1),
    9:  (1, 2),
    10: (1, 3),
    11: (1, 4),
    12: (1, 5),
    13: (1, 6),
    14: (1, 7),
    15: (1, 8),
    16: (1, 9),
    17: (1, 10),
    18: (1, 11),
    19: (1, 12),
    20: (1, 13),
    21: (1, 14),
}
# daemons.c:34

REGEN_RING_BONUS_PER_RING = 1
# daemons.c:35-38  -- unconditional +1 per ring of regeneration, every turn


# ---------------------------------------------------------------------------
# 7. Trap constants and names
# ---------------------------------------------------------------------------
T_DOOR = 0o0    # 0
T_ARROW = 0o1   # 1
T_SLEEP = 0o2   # 2
T_BEAR = 0o3    # 3
T_TELEP = 0o4   # 4
T_DART = 0o5    # 5
T_RUST = 0o6    # 6
T_MYST = 0o7    # 7
NTRAPS = 8
# rogue.h:196   -- the C writes these in octal (00..07)

MAXTRAPS = 10
# rogue.h:30    -- max traps generated on one level

F_TMASK = 0x07
# rogue.h:191   -- trap number mask in PLACE.p_flags
F_REAL = 0x10
# rogue.h:189   -- what you see is what you get (trap not yet a hidden fake)

# tr_name[] -- indexed by the trap constants above, in the same order.
TRAP_NAMES = [
    "a trapdoor",
    "an arrow trap",
    "a sleeping gas trap",
    "a beartrap",
    "a teleport trap",
    "a poison dart trap",
    "a rust trap",
    "a mysterious trap",
]
# extern.c:79   -- 8 entries, matches NTRAPS

TRAP_CHAR = "^"
# rogue.h:94    -- #define TRAP '^'


# ---------------------------------------------------------------------------
# Random numbers.  main.c:190
# ---------------------------------------------------------------------------

_rng = random.Random()


def seed_rng(seed):
    """Seed the generator.  Returns the seed actually used."""
    if seed is None:
        seed = _rng.randrange(1 << 30)
    _rng.seed(seed)
    return seed


def rnd(range_):
    """rnd: return a random number in the range 0 .. range_-1.   main.c:190
        return range == 0 ? 0 : abs((int) RN) % range;
    """
    if range_ == 0:
        return 0
    # A negative range still draws in the C -- abs(RN) % range consumes a
    # random number either way -- so it must draw here too, or a seeded
    # replay desynchronises wherever the game passes a negative (conn() can).
    return _rng.randrange(abs(range_))


def roll(number, sides):
    """roll: roll a number of dice.  main.c:200
        while (number--) dtotal += rnd(sides)+1;
    """
    total = 0
    for _ in range(number):
        total += rnd(sides) + 1
    return total


def spread(nm):
    """spread: return a number spread around nm.  misc.c:536
        return nm - nm / 20 + rnd(nm / 10);
    Note C integer division throughout.
    """
    return nm - nm // 20 + rnd(nm // 10)


# The damage strings in this source are written "1x4", not "1d4" -- see
# extern.c:166 INIT_STATS and the weapon tables.  Some tables use 'd'.
# Accept either, and accept multi-attack forms like "1x3/1x3".
def parse_dice(s):
    """Return a list of (number, sides) pairs from a damage string."""
    out = []
    if not s:
        return out
    for part in str(s).split('/'):
        part = part.strip()
        if not part:
            continue
        sep = 'x' if 'x' in part else ('d' if 'd' in part else None)
        if sep is None:
            continue
        a, _, b = part.partition(sep)
        # C atoi() semantics: a field that isn't a number is 0, not an error.
        # This matters -- the venus flytrap's table entry is literally
        # "%%%x0" (extern.c:199), and fight.c relies on atoi("%%%") == 0
        # while STILL running the attack loop, so swing() is rolled and a hit
        # deals 0 damage but sets ISHELD.  Skipping the pair instead would
        # make the flytrap unable to hit or hold the player at all.
        out.append((_atoi(a), _atoi(b)))
    return out


def _atoi(s):
    """C atoi(): leading integer, or 0 if there isn't one."""
    s = s.strip()
    i = 0
    if i < len(s) and s[i] in '+-':
        i += 1
    j = i
    while j < len(s) and s[j].isdigit():
        j += 1
    if j == i:
        return 0
    try:
        return int(s[:j])
    except ValueError:
        return 0


def roll_dice_string(s):
    """Sum every attack in a damage string."""
    return sum(roll(n, sides) for n, sides in parse_dice(s))


def dice_max(s):
    return sum(n * sides for n, sides in parse_dice(s))


# ---------------------------------------------------------------------------
# Core data types, mirroring the C structs in rogue.h
# ---------------------------------------------------------------------------

class Coord(object):
    """typedef struct coord { int x; int y; }   rogue.h:325"""

    __slots__ = ('x', 'y')

    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def copy(self):
        return Coord(self.x, self.y)

    def set(self, other):
        self.x = other.x
        self.y = other.y
        return self

    def __eq__(self, other):
        # the C macro ce(a,b)   rogue.h:66
        return other is not None and self.x == other.x and self.y == other.y

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.x, self.y))

    def __repr__(self):
        return "Coord(%d,%d)" % (self.x, self.y)


class Stats(object):
    """struct stats   rogue.h:344"""

    __slots__ = ('s_str', 's_exp', 's_lvl', 's_arm', 's_hpt', 's_dmg', 's_maxhp')

    def __init__(self, s_str=0, s_exp=0, s_lvl=0, s_arm=0, s_hpt=0, s_dmg="0x0",
                 s_maxhp=0):
        self.s_str = s_str
        self.s_exp = s_exp
        self.s_lvl = s_lvl
        self.s_arm = s_arm
        self.s_hpt = s_hpt
        self.s_dmg = s_dmg
        self.s_maxhp = s_maxhp

    def copy(self):
        return Stats(self.s_str, self.s_exp, self.s_lvl, self.s_arm,
                     self.s_hpt, self.s_dmg, self.s_maxhp)


# extern.c:166  #define INIT_STATS { 16, 0, 1, 10, 12, "1x4", 12 }
def init_stats():
    return Stats(16, 0, 1, 10, 12, "1x4", 12)


class Room(object):
    """struct room   rogue.h:333"""

    __slots__ = ('r_pos', 'r_max', 'r_gold', 'r_goldval', 'r_flags',
                 'r_nexits', 'r_exit')

    def __init__(self):
        self.r_pos = Coord()
        self.r_max = Coord()
        self.r_gold = Coord()
        self.r_goldval = 0
        self.r_flags = 0
        self.r_nexits = 0
        self.r_exit = [Coord() for _ in range(12)]


class Place(object):
    """typedef struct PLACE   rogue.h:424"""

    __slots__ = ('p_ch', 'p_flags', 'p_monst')

    def __init__(self):
        self.p_ch = ' '
        self.p_flags = F_REAL
        self.p_monst = None


class Thing(object):
    """The creature half of `union thing`.   rogue.h:356

    In the C this is a union shared with objects; splitting it in two is
    clearer in Python and the two halves are never used interchangeably.
    """

    __slots__ = ('t_pos', 't_turn', 't_type', 't_disguise', 't_oldch',
                 't_dest', 't_flags', 't_stats', 't_room', 't_pack',
                 't_reserved', 't_dead')

    def __init__(self):
        self.t_pos = Coord()
        self.t_turn = True
        self.t_type = ' '
        self.t_disguise = ' '
        self.t_oldch = ' '
        self.t_dest = None
        self.t_flags = 0
        self.t_stats = Stats()
        self.t_room = None
        self.t_pack = []
        self.t_reserved = 0
        self.t_dead = False


class Obj(object):
    """The object half of `union thing`.   rogue.h:370

    o_charges and o_goldval are the C's aliases for o_arm (rogue.h:415) -- the
    same storage under three names depending on object type.  Kept as real
    aliasing properties so ported code can use whichever name the C used.
    """

    __slots__ = ('o_type', 'o_pos', 'o_text', 'o_launch', 'o_packch',
                 'o_damage', 'o_hurldmg', 'o_count', 'o_which', 'o_hplus',
                 'o_dplus', 'o_arm', 'o_flags', 'o_group', 'o_label')

    def __init__(self):
        self.o_type = ' '
        self.o_pos = Coord()
        self.o_text = ""
        self.o_launch = NO_WEAPON
        self.o_packch = ' '
        self.o_damage = "0x0"
        self.o_hurldmg = "0x0"
        self.o_count = 1
        self.o_which = 0
        self.o_hplus = 0
        self.o_dplus = 0
        self.o_arm = 11
        self.o_flags = 0
        self.o_group = 0
        self.o_label = None

    # rogue.h:415  #define o_charges o_arm
    @property
    def o_charges(self):
        return self.o_arm

    @o_charges.setter
    def o_charges(self, v):
        self.o_arm = v

    # rogue.h:416  #define o_goldval o_arm
    @property
    def o_goldval(self):
        return self.o_arm

    @o_goldval.setter
    def o_goldval(self, v):
        self.o_arm = v


class ObjInfo(object):
    """struct obj_info   rogue.h:317 -- name, probability, worth, guess, known."""

    __slots__ = ('oi_name', 'oi_prob', 'oi_worth', 'oi_guess', 'oi_know')

    def __init__(self, name, prob=0, worth=0):
        self.oi_name = name
        self.oi_prob = prob
        self.oi_worth = worth
        self.oi_guess = None
        self.oi_know = False


class DelayedAction(object):
    """struct delayed_action   rogue.h:445"""

    __slots__ = ('d_type', 'd_func', 'd_arg', 'd_time')

    def __init__(self):
        self.d_type = EMPTY
        self.d_func = None
        self.d_arg = 0
        self.d_time = 0


def on(thing, flag):
    """rogue.h:71  #define on(thing,flag) ((((thing).t_flags & (flag)) != 0))"""
    return (thing.t_flags & flag) != 0


def step_ok(ch):
    """io.c:133 -- can something walk onto this character?"""
    if ch in (' ', '|', '-'):
        return False
    return not ch.isalpha()


def isupper_ch(ch):
    return isinstance(ch, str) and len(ch) == 1 and ch.isupper()


# ---------------------------------------------------------------------------
# Game state.  The C keeps all of this in globals (extern.c); here it lives on
# one object so that a self-test can spin up independent games in one process.
# ---------------------------------------------------------------------------

class Game(object):

    def __init__(self, seed=None):
        self.seed = seed_rng(seed)
        self.dnum = self.seed

        # the map
        self.places = [Place() for _ in range(MAXCOLS * MAXLINES)]
        self.rooms = [Room() for _ in range(MAXROOMS)]
        self.passages = [Room() for _ in range(MAXPASS)]
        for p in self.passages:
            p.r_flags = ISGONE | ISDARK          # extern.c:174

        # the hero
        self.player = Thing()
        self.player.t_type = PLAYER
        self.player.t_disguise = PLAYER
        self.max_stats = init_stats()
        self.player.t_stats = init_stats()
        self.player.t_pack = []

        self.cur_armor = None
        self.cur_weapon = None
        self.cur_ring = [None, None]
        self.last_pick = None
        self.l_last_pick = None

        # level contents
        self.mlist = []
        self.lvl_obj = []
        self.stairs = Coord()
        self.oldpos = Coord()
        self.delta = Coord()
        self.oldrp = None
        self.proom = None

        # counters and flags (extern.c)
        self.level = 1
        self.max_level = 1
        self.purse = 0
        self.ntraps = 0
        self.no_food = 0
        self.food_left = HUNGERTIME
        self.hungry_state = F_OKAY
        self.inpack = 0
        self.total = 0
        self.no_move = 0
        self.no_command = 0
        self.count = 0
        self.quiet = 0
        self.group = 2
        # extern.c:18  `after`   -- true if we want the after-daemons to run;
        #                           reset at the top of every command
        # extern.c:397 `between` -- a PERSISTENT counter used only by rollwand()
        # These are two different globals in the C and must not be conflated:
        # sharing one field means every command resets the wandering-monster
        # counter, and no wanderer ever spawns.
        self.after = True
        self.between = 0
        self.amulet = False
        self.playing = True
        self.running = False
        self.to_death = False
        self.kamikaze = False
        self.has_hit = False
        self.door_stop = False
        self.firstmove = False
        self.seenstairs = False
        self.take = 0
        self.move_on = False
        self.n_objs = 0
        self.runch = ' '
        self.dir_ch = ' '
        self.last_comm = ' '
        self.l_last_comm = ' '
        self.last_dir = ' '
        self.l_last_dir = ' '
        self.max_hit = 0
        self.vf_hit = 0
        self.pack_used = [False] * 26
        self.win = False
        self.death_reason = None
        self.turns = 0

        # options (options.c) -- the ones that affect play
        self.terse = False
        self.jump = False
        self.see_floor = True
        self.passgo = False
        self.tombstone = True
        self.whoami = os.environ.get("USERNAME") or os.environ.get("USER") or "Rodney"

        # daemons and fuses (daemon.c)
        self.d_list = [DelayedAction() for _ in range(MAXDAEMONS)]
        self.fuse_list = [DelayedAction() for _ in range(MAXDAEMONS)]
        self.demoncnt = 0

        # item identification state -- built per game by init_names() etc.
        self.pot_info = []
        self.scr_info = []
        self.ring_info = []
        self.ws_info = []
        self.arm_info = []
        self.weap_info = []
        self.p_colors = []
        self.s_names = []
        self.r_stones = []
        self.ws_type = []
        self.ws_made = []

        # message plumbing, consumed by the renderer
        self.msg_queue = []
        self.msg_history = []
        self.msg_current = ""

        self.renderer = None
        self.headless = False

    # -- map accessors, replacing the C's INDEX/chat/flat/moat macros --------

    def _idx(self, y, x):
        # rogue.h:76  #define INDEX(y,x) (&places[((x) << 5) + (y)])
        return (x << 5) + y

    def place(self, y, x):
        return self.places[(x << 5) + y]

    def chat(self, y, x):
        return self.places[(x << 5) + y].p_ch

    def set_chat(self, y, x, ch):
        self.places[(x << 5) + y].p_ch = ch

    def flat(self, y, x):
        return self.places[(x << 5) + y].p_flags

    def set_flat(self, y, x, v):
        self.places[(x << 5) + y].p_flags = v

    def moat(self, y, x):
        return self.places[(x << 5) + y].p_monst

    def set_moat(self, y, x, m):
        self.places[(x << 5) + y].p_monst = m

    def winat(self, y, x):
        # rogue.h:65
        m = self.moat(y, x)
        return m.t_disguise if m is not None else self.chat(y, x)

    def in_bounds(self, y, x):
        return 0 <= y < NUMLINES and 0 <= x < NUMCOLS

    # -- convenience aliases matching the C macros --------------------------

    @property
    def hero(self):
        return self.player.t_pos

    @property
    def pstats(self):
        return self.player.t_stats

    @property
    def pack(self):
        return self.player.t_pack

    def goldcalc(self):
        # rogue.h:72  #define GOLDCALC (rnd(50 + 10 * level) + 2)
        return rnd(50 + 10 * self.level) + 2

    def is_ring(self, hand, r):
        # rogue.h:73
        return self.cur_ring[hand] is not None and self.cur_ring[hand].o_which == r
    def is_wearing(self, r):
        # rogue.h:74
        return self.is_ring(LEFT, r) or self.is_ring(RIGHT, r)


# ---------------------------------------------------------------------------
# Screen buffer -- the curses shim.
#
# PORT NOTE: this is the single most important structural decision in the port.
#
# The original leans on curses far harder than it looks.  `places[]` holds the
# TRUE dungeon, but what the player *remembers* is never stored anywhere -- it
# is simply whatever characters are currently on the curses screen.  The game
# reads it back with inch() and tests it (leave_room() checks `CCHAR(inch())`
# to decide whether to blank a tile; enter_room() compares inch() against the
# real char to avoid redundant writes).  Erasing a monster means redrawing
# t_oldch, the character that monster is standing on.
#
# So porting to pygame is not a matter of swapping the drawing calls: the
# renderer cannot be the memory, because pygame has no readable character
# cell grid.  Instead this class reproduces exactly the slice of curses the
# game actually uses -- a readable NUMLINES x NUMCOLS character buffer -- and
# the pygame renderer becomes a pure function of it.  Every mvaddch/addch/inch
# in the C ports across one-for-one, and the display logic needs no rethinking.
#
# The `standout` plane is carried alongside because the C uses standout() to
# mark monsters detected but not seen (SEEMONST) and unreal passages.
# ---------------------------------------------------------------------------

class Screen(object):

    __slots__ = ('ch', 'so', 'cur_y', 'cur_x', '_standout')

    def __init__(self):
        self.ch = [[' '] * NUMCOLS for _ in range(NUMLINES)]
        self.so = [[False] * NUMCOLS for _ in range(NUMLINES)]
        self.cur_y = 0
        self.cur_x = 0
        self._standout = False

    def clear(self):
        for row in self.ch:
            for i in range(NUMCOLS):
                row[i] = ' '
        for row in self.so:
            for i in range(NUMCOLS):
                row[i] = False
        self.cur_y = 0
        self.cur_x = 0

    # -- cursor ------------------------------------------------------------

    def move(self, y, x):
        self.cur_y = y
        self.cur_x = x

    def standout(self):
        self._standout = True

    def standend(self):
        self._standout = False

    # -- character access --------------------------------------------------

    def inch(self, y=None, x=None):
        """curses inch(): read the character at the cursor (or at y,x)."""
        if y is None:
            y, x = self.cur_y, self.cur_x
        if not (0 <= y < NUMLINES and 0 <= x < NUMCOLS):
            return ' '
        return self.ch[y][x]

    def addch(self, c):
        """curses addch(): write at the cursor and advance it."""
        y, x = self.cur_y, self.cur_x
        if 0 <= y < NUMLINES and 0 <= x < NUMCOLS:
            self.ch[y][x] = c
            self.so[y][x] = self._standout
        self.cur_x += 1
        if self.cur_x >= NUMCOLS:
            self.cur_x = NUMCOLS - 1

    def mvaddch(self, y, x, c):
        self.move(y, x)
        self.addch(c)

    def mvinch(self, y, x):
        return self.inch(y, x)

    def addstr(self, s):
        for c in s:
            self.addch(c)

    def mvaddstr(self, y, x, s):
        self.move(y, x)
        self.addstr(s)


# ---------------------------------------------------------------------------
# Messages.  Ported from the message half of io.c
#
# PORT NOTE: the C writes messages straight onto line 0 of the curses screen and
# blocks on a keypress for --More-- when a second message arrives before the
# first was read.  Here messages accumulate in a queue on the Game and the
# renderer drains it, so the game logic never blocks on input.  addmsg/endmsg/
# msg keep their original meanings so ported call sites are unchanged.
# ---------------------------------------------------------------------------

MAXMSG = NUMCOLS - 20           # io.c:23
MSG_HISTORY = 200


def addmsg(game, text):
    """io.c:60 -- append to the message under construction."""
    game.msg_current += text


def endmsg(game):
    """io.c:75 -- finish the message under construction and post it."""
    text = game.msg_current
    game.msg_current = ""
    if not text:
        return
    game.msg_history.append(text)
    if len(game.msg_history) > MSG_HISTORY:
        del game.msg_history[0:len(game.msg_history) - MSG_HISTORY]
    game.msg_queue.append(text)


def msg(game, text=""):
    """io.c:31 -- post a message.  An empty message clears the line."""
    if text == "":
        game.msg_current = ""
        game.msg_queue.append("")
        return
    addmsg(game, text)
    endmsg(game)


def unctrl(ch):
    """curses unctrl(): a PRINTABLE form of a key.

    The C calls this everywhere it echoes a keystroke back at the player
    (command.c:468 illcom, and the help and identify messages).  Without it a
    control character ends up inside a message string, and pygame refuses to
    render one -- font.render("") raises "Text has zero width" -- which
    takes the whole game down when that message reaches the top of the queue.
    """
    if not ch:
        return ""
    c = ord(ch[0])
    if c < 32:
        return "^" + chr(c + 64)
    if c == 127:
        return "^?"
    return ch[0]


def prname(mname, upper):
    """fight.c:520 -- the print name of a combatant."""
    tbuf = "you" if mname is None else mname
    if upper and tbuf:
        tbuf = tbuf[0].upper() + tbuf[1:]
    return tbuf


def vowelstr(s):
    """misc.c:445 -- "n" if the string starts with a vowel, for "a"/"an"."""
    return "n" if s[:1] in "aAeEiIoOuU" else ""


def num(n1, n2, type_ch):
    """weapons.c:204 -- the plus number for armor/weapons.

        sprintf(numbuf, n1 < 0 ? "%d" : "+%d", n1);
        if (type == WEAPON)
            sprintf(&numbuf[strlen(numbuf)], n2 < 0 ? ",%d" : ",+%d", n2);

    Weapons carry BOTH numbers -- to-hit and damage -- as "+1,+1".
    """
    buf = "%d" % n1 if n1 < 0 else "+%d" % n1
    if type_ch == WEAPON:
        buf += ",%d" % n2 if n2 < 0 else ",+%d" % n2
    return buf


def choose_str(game, ts, ns):
    """misc.c:640 -- first string if tripping, second otherwise."""
    return ts if on(game.player, ISHALU) else ns


# ---------------------------------------------------------------------------
# Level generation.  Ported from rooms.c, passages.c and new_level.c
# ---------------------------------------------------------------------------

TREAS_ROOM = 20                 # new_level.c:18  one chance in 20 of a treasure room
MAXTREAS = 10                   # new_level.c:19
MINTREAS = 2                    # new_level.c:20
MAXTRIES = 10                   # new_level.c:181  tries to place a monster
GOLDGRP = 1                     # rooms.c:24


# ---------------------------------------------------------------------------
# rooms.c
# ---------------------------------------------------------------------------

def do_rooms(game):
    """rooms.c:30 -- create rooms and corridors with a connectivity graph."""
    bsze = Coord(NUMCOLS // 3, NUMLINES // 3)

    for rp in game.rooms:
        rp.r_goldval = 0
        rp.r_nexits = 0
        rp.r_flags = 0

    # Put the gone rooms, if any, on the level.  rooms.c:52
    left_out = rnd(4)
    for _ in range(left_out):
        game.rooms[rnd_room(game)].r_flags |= ISGONE

    for i in range(MAXROOMS):
        rp = game.rooms[i]
        # Find upper left corner of box that this room goes in.  rooms.c:64
        top = Coord((i % 3) * bsze.x + 1, (i // 3) * bsze.y)

        if rp.r_flags & ISGONE:
            # Place a gone room, keeping a blank line for passage drawing.
            while True:
                rp.r_pos.x = top.x + rnd(bsze.x - 2) + 1
                rp.r_pos.y = top.y + rnd(bsze.y - 2) + 1
                rp.r_max.x = -NUMCOLS
                rp.r_max.y = -NUMLINES
                if rp.r_pos.y > 0 and rp.r_pos.y < NUMLINES - 1:
                    break
            continue

        # set room type.  rooms.c:85
        if rnd(10) < game.level - 1:
            rp.r_flags |= ISDARK
            if rnd(15) == 0:
                rp.r_flags = ISMAZE     # note: assignment, not |=, as in the C

        if rp.r_flags & ISMAZE:
            rp.r_max.x = bsze.x - 1
            rp.r_max.y = bsze.y - 1
            rp.r_pos.x = top.x
            if rp.r_pos.x == 1:
                rp.r_pos.x = 0
            rp.r_pos.y = top.y
            if rp.r_pos.y == 0:
                rp.r_pos.y += 1
                rp.r_max.y -= 1
        else:
            while True:
                rp.r_max.x = rnd(bsze.x - 4) + 4
                rp.r_max.y = rnd(bsze.y - 4) + 4
                rp.r_pos.x = top.x + rnd(bsze.x - rp.r_max.x)
                rp.r_pos.y = top.y + rnd(bsze.y - rp.r_max.y)
                if rp.r_pos.y != 0:
                    break

        draw_room(game, rp)

        # Put the gold in.  rooms.c:120
        if rnd(2) == 0 and (not game.amulet or game.level >= game.max_level):
            gold = Obj()
            gold.o_goldval = game.goldcalc()
            rp.r_goldval = gold.o_goldval
            find_floor(game, rp, rp.r_gold, 0, False)
            gold.o_pos = rp.r_gold.copy()
            game.set_chat(rp.r_gold.y, rp.r_gold.x, GOLD)
            gold.o_flags = ISMANY
            gold.o_group = GOLDGRP
            gold.o_type = GOLD
            game.lvl_obj.append(gold)

        # Put the monster in.  rooms.c:137
        if rnd(100) < (80 if rp.r_goldval > 0 else 25):
            mp = Coord()
            find_floor(game, rp, mp, 0, True)
            tp = Thing()
            new_monster(game, tp, randmonster(game, False), mp)
            give_pack(game, tp)


def draw_room(game, rp):
    """rooms.c:152"""
    if rp.r_flags & ISMAZE:
        do_maze(game, rp)
        return

    vert(game, rp, rp.r_pos.x)                          # left side
    vert(game, rp, rp.r_pos.x + rp.r_max.x - 1)         # right side
    horiz(game, rp, rp.r_pos.y)                         # top
    horiz(game, rp, rp.r_pos.y + rp.r_max.y - 1)        # bottom

    for y in range(rp.r_pos.y + 1, rp.r_pos.y + rp.r_max.y - 1):
        for x in range(rp.r_pos.x + 1, rp.r_pos.x + rp.r_max.x - 1):
            game.set_chat(y, x, FLOOR)


def vert(game, rp, startx):
    """rooms.c:177"""
    for y in range(rp.r_pos.y + 1, rp.r_max.y + rp.r_pos.y):
        game.set_chat(y, startx, VWALL)


def horiz(game, rp, starty):
    """rooms.c:191"""
    for x in range(rp.r_pos.x, rp.r_pos.x + rp.r_max.x):
        game.set_chat(starty, x, HWALL)


class _Spot(object):
    """typedef struct spot -- position matrix for maze positions.  rooms.c:17"""
    __slots__ = ('nexits', 'exits', 'used')

    def __init__(self):
        self.nexits = 0
        self.exits = [Coord() for _ in range(4)]
        self.used = False


def do_maze(game, rp):
    """rooms.c:211 -- dig a maze."""
    maze = [[_Spot() for _ in range(NUMCOLS // 3 + 1)]
            for _ in range(NUMLINES // 3 + 1)]

    maxy = rp.r_max.y
    maxx = rp.r_max.x
    starty_o = rp.r_pos.y
    startx_o = rp.r_pos.x
    starty = (rnd(rp.r_max.y) // 2) * 2
    startx = (rnd(rp.r_max.x) // 2) * 2
    pos = Coord(startx + startx_o, starty + starty_o)
    putpass(game, pos)
    dig(game, maze, starty, startx, maxy, maxx, starty_o, startx_o)


def dig(game, maze, y, x, maxy, maxx, starty_o, startx_o):
    """rooms.c:242 -- dig out from around where we are now, if possible.

    PORT NOTE: the C recurses.  A maze room is at most 7 x 25 cells so the
    depth is bounded, but Python's default recursion limit plus the fact that
    numpass() below is also recursive makes an explicit stack the safer port.
    The carving order and the RNG call sequence are identical to the C, which
    is what actually matters for reproducing a seeded level.
    """
    delta = ((2, 0), (-2, 0), (0, 2), (0, -2))          # rooms.c:249
    stack = [(y, x)]
    while stack:
        y, x = stack[-1]
        cnt = 0
        nexty = nextx = 0
        for dy, dx in delta:
            newy = y + dy
            newx = x + dx
            if newy < 0 or newy > maxy or newx < 0 or newx > maxx:
                continue
            if game.flat(newy + starty_o, newx + startx_o) & F_PASS:
                continue
            cnt += 1
            if rnd(cnt) == 0:
                nexty = newy
                nextx = newx
        if cnt == 0:
            stack.pop()
            continue
        accnt_maze(maze, y, x, nexty, nextx)
        accnt_maze(maze, nexty, nextx, y, x)
        if nexty == y:
            pos = Coord(0, y + starty_o)
            if nextx - x < 0:
                pos.x = nextx + startx_o + 1
            else:
                pos.x = nextx + startx_o - 1
        else:
            pos = Coord(x + startx_o, 0)
            if nexty - y < 0:
                pos.y = nexty + starty_o + 1
            else:
                pos.y = nexty + starty_o - 1
        putpass(game, pos)
        putpass(game, Coord(nextx + startx_o, nexty + starty_o))
        stack.append((nexty, nextx))


def accnt_maze(maze, y, x, ny, nx):
    """rooms.c:303 -- account for maze exits.

    PORT NOTE: this is a no-op in the original and is ported as one.  The C
    walks `exits[0 .. nexits-1]` looking for a duplicate, then writes the new
    exit at index nexits -- but never increments nexits.  So nexits stays 0
    forever, the loop never executes, and the recorded exits are never read by
    anything.  Kept (rather than deleted) to document the original behaviour.
    """
    sp = maze[y][x]
    for i in range(sp.nexits):
        cp = sp.exits[i]
        if cp.y == ny and cp.x == nx:
            return
    cp = sp.exits[sp.nexits]
    cp.y = ny
    cp.x = nx


def rnd_pos(rp, cp):
    """rooms.c:324 -- pick a random spot in a room."""
    cp.x = rp.r_pos.x + rnd(rp.r_max.x - 2) + 1
    cp.y = rp.r_pos.y + rnd(rp.r_max.y - 2) + 1


def find_floor(game, rp, cp, limit, monst):
    """rooms.c:336 -- find a valid floor spot.  rp None means pick a new room
    each time around the loop.  Mutates cp; returns True/False like the C."""
    pickroom = (rp is None)
    compchar = 0
    if not pickroom:
        compchar = PASSAGE if (rp.r_flags & ISMAZE) else FLOOR
    cnt = limit
    while True:
        if limit:
            if cnt == 0:
                return False
            cnt -= 1
        if pickroom:
            rp = game.rooms[rnd_room(game)]
            compchar = PASSAGE if (rp.r_flags & ISMAZE) else FLOOR
        rnd_pos(rp, cp)
        pp = game.place(cp.y, cp.x)
        if monst:
            if pp.p_monst is None and step_ok(pp.p_ch):
                return True
        elif pp.p_ch == compchar:
            return True


def enter_room(game, cp):
    """rooms.c:369 -- executed whenever you appear in a room."""
    rp = roomin(game, cp)
    game.proom = rp
    door_open(game, rp)
    scr = game.screen
    if not (rp.r_flags & ISDARK) and not on(game.player, ISBLIND):
        for y in range(rp.r_pos.y, rp.r_max.y + rp.r_pos.y):
            scr.move(y, rp.r_pos.x)
            for x in range(rp.r_pos.x, rp.r_max.x + rp.r_pos.x):
                tp = game.moat(y, x)
                ch = game.chat(y, x)
                if tp is None:
                    if scr.inch() != ch:
                        scr.addch(ch)
                    else:
                        scr.move(y, x + 1)
                else:
                    tp.t_oldch = ch
                    if not see_monst(game, tp):
                        if on(game.player, SEEMONST):
                            scr.standout()
                            scr.addch(tp.t_disguise)
                            scr.standend()
                        else:
                            scr.addch(ch)
                    else:
                        scr.addch(tp.t_disguise)


def leave_room(game, cp):
    """rooms.c:410 -- code for when we exit a room."""
    rp = game.proom
    if rp is None or (rp.r_flags & ISMAZE):
        return

    if rp.r_flags & ISGONE:
        floor = PASSAGE
    elif not (rp.r_flags & ISDARK) or on(game.player, ISBLIND):
        floor = FLOOR
    else:
        floor = ' '

    game.proom = game.passages[game.flat(cp.y, cp.x) & F_PNUM]
    scr = game.screen
    for y in range(rp.r_pos.y, rp.r_max.y + rp.r_pos.y):
        for x in range(rp.r_pos.x, rp.r_max.x + rp.r_pos.x):
            scr.move(y, x)
            ch = scr.inch()
            if ch == FLOOR:
                if floor == ' ' and ch != ' ':
                    scr.addch(' ')
            else:
                # to check for a monster we strip the standout bit
                if isupper_ch(ch):
                    if on(game.player, SEEMONST):
                        scr.standout()
                        scr.addch(ch)
                        scr.standend()
                        continue
                    pp = game.place(y, x)
                    scr.addch(DOOR if pp.p_ch == DOOR else floor)
    door_open(game, rp)


# ---------------------------------------------------------------------------
# passages.c
# ---------------------------------------------------------------------------

# passages.c:33 -- which of the 9 rooms are adjacent to which
_ROOM_CONN = (
    (0, 1, 0, 1, 0, 0, 0, 0, 0),
    (1, 0, 1, 0, 1, 0, 0, 0, 0),
    (0, 1, 0, 0, 0, 1, 0, 0, 0),
    (1, 0, 0, 0, 1, 0, 1, 0, 0),
    (0, 1, 0, 1, 0, 1, 0, 1, 0),
    (0, 0, 1, 0, 1, 0, 0, 0, 1),
    (0, 0, 0, 1, 0, 0, 0, 1, 0),
    (0, 0, 0, 0, 1, 0, 1, 0, 1),
    (0, 0, 0, 0, 0, 1, 0, 1, 0),
)


class _Rdes(object):
    __slots__ = ('conn', 'isconn', 'ingraph')

    def __init__(self, conn):
        self.conn = conn
        self.isconn = [False] * MAXROOMS
        self.ingraph = False


def do_passages(game):
    """passages.c:22 -- draw all the passages on a level."""
    rdes = [_Rdes(_ROOM_CONN[i]) for i in range(MAXROOMS)]
    r2 = None

    # starting with one room, connect it to a random adjacent room and then
    # pick a new room to start with.  passages.c:60
    roomcount = 1
    r1 = rdes[rnd(MAXROOMS)]
    r1.ingraph = True
    while roomcount < MAXROOMS:
        j = 0
        for i in range(MAXROOMS):
            if r1.conn[i] and not rdes[i].ingraph:
                j += 1
                if rnd(j) == 0:
                    r2 = rdes[i]
        if j == 0:
            while True:
                r1 = rdes[rnd(MAXROOMS)]
                if r1.ingraph:
                    break
        else:
            r2.ingraph = True
            i = rdes.index(r1)
            j = rdes.index(r2)
            conn(game, i, j)
            r1.isconn[j] = True
            r2.isconn[i] = True
            roomcount += 1

    # add a few extra passages so there isn't always one unique route
    for _ in range(rnd(5), 0, -1):
        r1 = rdes[rnd(MAXROOMS)]
        j = 0
        for i in range(MAXROOMS):
            if r1.conn[i] and not r1.isconn[i]:
                j += 1
                if rnd(j) == 0:
                    r2 = rdes[i]
        if j != 0:
            i = rdes.index(r1)
            j = rdes.index(r2)
            conn(game, i, j)
            r1.isconn[j] = True
            r2.isconn[i] = True

    passnum(game)


def conn(game, r1, r2):
    """passages.c:128 -- draw a corridor from a room in a certain direction."""
    if r1 < r2:
        rm = r1
        direc = 'r' if r1 + 1 == r2 else 'd'
    else:
        rm = r2
        direc = 'r' if r2 + 1 == r1 else 'd'
    rpf = game.rooms[rm]

    delta = Coord()
    turn_delta = Coord()
    spos = Coord()
    epos = Coord()

    if direc == 'd':
        rmt = rm + 3
        rpt = game.rooms[rmt]
        delta.x, delta.y = 0, 1
        spos.x, spos.y = rpf.r_pos.x, rpf.r_pos.y
        epos.x, epos.y = rpt.r_pos.x, rpt.r_pos.y
        if not (rpf.r_flags & ISGONE):
            while True:
                spos.x = rpf.r_pos.x + rnd(rpf.r_max.x - 2) + 1
                spos.y = rpf.r_pos.y + rpf.r_max.y - 1
                if not ((rpf.r_flags & ISMAZE) and
                        not (game.flat(spos.y, spos.x) & F_PASS)):
                    break
        if not (rpt.r_flags & ISGONE):
            while True:
                epos.x = rpt.r_pos.x + rnd(rpt.r_max.x - 2) + 1
                if not ((rpt.r_flags & ISMAZE) and
                        not (game.flat(epos.y, epos.x) & F_PASS)):
                    break
        distance = abs(spos.y - epos.y) - 1
        turn_delta.y = 0
        turn_delta.x = 1 if spos.x < epos.x else -1
        turn_distance = abs(spos.x - epos.x)
    else:
        rmt = rm + 1
        rpt = game.rooms[rmt]
        delta.x, delta.y = 1, 0
        spos.x, spos.y = rpf.r_pos.x, rpf.r_pos.y
        epos.x, epos.y = rpt.r_pos.x, rpt.r_pos.y
        if not (rpf.r_flags & ISGONE):
            while True:
                spos.x = rpf.r_pos.x + rpf.r_max.x - 1
                spos.y = rpf.r_pos.y + rnd(rpf.r_max.y - 2) + 1
                if not ((rpf.r_flags & ISMAZE) and
                        not (game.flat(spos.y, spos.x) & F_PASS)):
                    break
        if not (rpt.r_flags & ISGONE):
            while True:
                epos.y = rpt.r_pos.y + rnd(rpt.r_max.y - 2) + 1
                if not ((rpt.r_flags & ISMAZE) and
                        not (game.flat(epos.y, epos.x) & F_PASS)):
                    break
        distance = abs(spos.x - epos.x) - 1
        turn_delta.y = 1 if spos.y < epos.y else -1
        turn_delta.x = 0
        turn_distance = abs(spos.y - epos.y)

    # passages.c:221 -- unconditional; rnd() now draws for negative ranges
    # too, so this stays in step with the C.  turn_spot is unused when
    # distance <= 0 because the digging loop does not run.
    turn_spot = rnd(distance - 1) + 1

    # Draw the doors on either side, or just #'s if the rooms are gone.
    if not (rpf.r_flags & ISGONE):
        door(game, rpf, spos)
    else:
        putpass(game, spos)
    if not (rpt.r_flags & ISGONE):
        door(game, rpt, epos)
    else:
        putpass(game, epos)

    curr = Coord(spos.x, spos.y)
    while distance > 0:
        curr.x += delta.x
        curr.y += delta.y
        if distance == turn_spot:
            while turn_distance > 0:
                turn_distance -= 1
                putpass(game, curr)
                curr.x += turn_delta.x
                curr.y += turn_delta.y
        putpass(game, curr)
        distance -= 1
    curr.x += delta.x
    curr.y += delta.y
    if curr != epos:
        msg(game, "warning, connectivity problem on this level")


def putpass(game, cp):
    """passages.c:258 -- add a passage character or secret passage here."""
    pp = game.place(cp.y, cp.x)
    pp.p_flags |= F_PASS
    if rnd(10) + 1 < game.level and rnd(40) == 0:
        pp.p_flags &= ~F_REAL
    else:
        pp.p_ch = PASSAGE


def door(game, rm, cp):
    """passages.c:277 -- add a door, or possibly a secret door."""
    if rm.r_nexits < len(rm.r_exit):
        rm.r_exit[rm.r_nexits] = cp.copy()
    rm.r_nexits += 1

    if rm.r_flags & ISMAZE:
        return

    pp = game.place(cp.y, cp.x)
    if rnd(10) + 1 < game.level and rnd(5) == 0:
        if cp.y == rm.r_pos.y or cp.y == rm.r_pos.y + rm.r_max.y - 1:
            pp.p_ch = HWALL
        else:
            pp.p_ch = VWALL
        pp.p_flags &= ~F_REAL
    else:
        pp.p_ch = DOOR


def passnum(game):
    """passages.c:347 -- assign a number to each passageway."""
    state = {'pnum': 0, 'newpnum': False}
    for rp in game.passages:
        rp.r_nexits = 0
    for rp in game.rooms:
        for i in range(rp.r_nexits):
            state['newpnum'] = True
            numpass(game, rp.r_exit[i].y, rp.r_exit[i].x, state)


def numpass(game, y, x, state):
    """passages.c:370 -- number a passageway square and its brethren.

    PORT NOTE: the C recurses on all four neighbours.  A passage can easily run
    hundreds of cells, which blows Python's default recursion limit, so this is
    an explicit stack.  Order of traversal is preserved (y+1, y-1, x+1, x-1
    pushed in reverse so they pop in the C's order).
    """
    stack = [(y, x)]
    while stack:
        y, x = stack.pop()
        if x >= NUMCOLS or x < 0 or y >= NUMLINES or y <= 0:
            continue
        fl = game.flat(y, x)
        if fl & F_PNUM:
            continue
        if state['newpnum']:
            state['pnum'] += 1
            state['newpnum'] = False
        ch = game.chat(y, x)
        if ch == DOOR or (not (fl & F_REAL) and ch in (VWALL, HWALL)):
            rp = game.passages[state['pnum']]
            if rp.r_nexits < len(rp.r_exit):
                rp.r_exit[rp.r_nexits] = Coord(x, y)
            rp.r_nexits += 1
        elif not (fl & F_PASS):
            continue
        game.set_flat(y, x, game.flat(y, x) | state['pnum'])
        stack.append((y, x - 1))
        stack.append((y, x + 1))
        stack.append((y - 1, x))
        stack.append((y + 1, x))


# ---------------------------------------------------------------------------
# new_level.c
# ---------------------------------------------------------------------------

def new_level(game):
    """new_level.c:23 -- dig and draw a new level."""
    game.player.t_flags &= ~ISHELD
    if game.level > game.max_level:
        game.max_level = game.level

    for pp in game.places:
        pp.p_ch = ' '
        pp.p_flags = F_REAL
        pp.p_monst = None
    game.screen.clear()

    game.mlist = []
    game.lvl_obj = []

    do_rooms(game)
    do_passages(game)
    game.no_food += 1
    put_things(game)

    # Place the traps.  new_level.c:56
    if rnd(10) < game.level:
        game.ntraps = rnd(game.level // 4) + 1
        if game.ntraps > MAXTRAPS:
            game.ntraps = MAXTRAPS
        i = game.ntraps
        while i:
            i -= 1
            while True:
                find_floor(game, None, game.stairs, 0, False)
                if not (game.chat(game.stairs.y, game.stairs.x) != FLOOR and
                        (game.flat(game.stairs.y, game.stairs.x) & F_REAL)):
                    break
            y, x = game.stairs.y, game.stairs.x
            fl = game.flat(y, x)
            fl &= ~(F_REAL | F_TMASK)
            fl |= rnd(NTRAPS)
            game.set_flat(y, x, fl)

    # Place the staircase down.  new_level.c:85
    find_floor(game, None, game.stairs, 0, False)
    game.set_chat(game.stairs.y, game.stairs.x, STAIRS)
    game.seenstairs = False

    for tp in game.mlist:
        tp.t_room = roomin(game, tp.t_pos)

    find_floor(game, None, game.player.t_pos, 0, True)
    enter_room(game, game.player.t_pos)
    game.screen.mvaddch(game.player.t_pos.y, game.player.t_pos.x, PLAYER)
    if on(game.player, SEEMONST):
        turn_see(game, False)
    if on(game.player, ISHALU):
        visuals(game)


def rnd_room(game):
    """new_level.c:104 -- pick a room that is really there."""
    while True:
        rm = rnd(MAXROOMS)
        if not (game.rooms[rm].r_flags & ISGONE):
            return rm


def put_things(game):
    """new_level.c:121 -- put potions and scrolls on this level."""
    # Once you have the amulet the only way to get new stuff is to go down.
    if game.amulet and game.level < game.max_level:
        return

    if rnd(TREAS_ROOM) == 0:
        treas_room(game)

    for _ in range(MAXOBJ):
        if rnd(100) < 36:
            obj = new_thing(game)
            game.lvl_obj.append(obj)
            find_floor(game, None, obj.o_pos, 0, False)
            game.set_chat(obj.o_pos.y, obj.o_pos.x, obj.o_type)

    # Deep enough and still no amulet: drop one.  new_level.c:158
    if game.level >= AMULETLEVEL and not game.amulet:
        obj = Obj()
        game.lvl_obj.append(obj)
        obj.o_hplus = 0
        obj.o_dplus = 0
        obj.o_damage = "0x0"
        obj.o_hurldmg = "0x0"
        obj.o_arm = 11
        obj.o_type = AMULET
        find_floor(game, None, obj.o_pos, 0, False)
        game.set_chat(obj.o_pos.y, obj.o_pos.x, AMULET)


def treas_room(game):
    """new_level.c:185 -- add a treasure room."""
    rp = game.rooms[rnd_room(game)]
    spots = (rp.r_max.y - 2) * (rp.r_max.x - 2) - MINTREAS
    if spots > (MAXTREAS - MINTREAS):
        spots = MAXTREAS - MINTREAS
    if spots < 1:
        spots = 1
    num_monst = nm = rnd(spots) + MINTREAS
    while nm:
        nm -= 1
        mp = Coord()
        find_floor(game, rp, mp, 2 * MAXTRIES, False)
        tp = new_thing(game)
        tp.o_pos = mp.copy()
        game.lvl_obj.append(tp)
        game.set_chat(mp.y, mp.x, tp.o_type)

    # fill up the room with monsters from the next level down
    nm = rnd(spots) + MINTREAS
    if nm < num_monst + 2:
        nm = num_monst + 2
    spots = (rp.r_max.y - 2) * (rp.r_max.x - 2)
    if nm > spots:
        nm = spots
    game.level += 1
    while nm > 0:
        nm -= 1
        mp = Coord()
        if find_floor(game, rp, mp, MAXTRIES, True):
            tp = Thing()
            new_monster(game, tp, randmonster(game, False), mp)
            tp.t_flags |= ISMEAN      # no sloughers in THIS room
            give_pack(game, tp)
    game.level -= 1


# ---------------------------------------------------------------------------
# Monsters and pursuit.  Ported from monsters.c and chase.c
# ---------------------------------------------------------------------------

DRAGONSHOT = 5                  # chase.c:19  one chance in 5 a dragon flames


def dist(y1, x1, y2, x2):
    """chase.c:497 -- squared distance; only ever used comparatively."""
    return (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1)


def dist_cp(c1, c2):
    """chase.c:508"""
    return dist(c1.y, c1.x, c2.y, c2.x)


def sign(nm):
    """misc.c -- return the sign of a number."""
    if nm < 0:
        return -1
    return 1 if nm > 0 else 0


def randmonster(game, wander):
    """monsters.c:37 -- pick a monster; lower level means meaner monster.

    LVL_MONS/WAND_MONS are 26-entry tables; a space stands for the C's 0,
    meaning "not a valid wandering monster, re-roll".
    """
    mons = WAND_MONS if wander else LVL_MONS
    while True:
        d = game.level + (rnd(10) - 6)
        if d < 0:
            d = rnd(5)
        if d > 25:
            d = rnd(5) + 21
        if mons[d] != ' ':
            return mons[d]


def monster_info(type_ch):
    """Table row for a monster letter."""
    return MONSTERS[ord(type_ch) - ord('A')]


def new_monster(game, tp, type_ch, cp):
    """monsters.c:60 -- pick a new monster and add it to the list."""
    lev_add = game.level - AMULETLEVEL
    if lev_add < 0:
        lev_add = 0
    game.mlist.append(tp)
    tp.t_type = type_ch
    tp.t_disguise = type_ch
    tp.t_pos = cp.copy()
    tp.t_oldch = game.screen.inch(cp.y, cp.x)
    tp.t_room = roomin(game, cp)
    game.set_moat(cp.y, cp.x, tp)

    mp = monster_info(type_ch)
    st = tp.t_stats
    st.s_lvl = mp['lvl'] + lev_add
    st.s_maxhp = st.s_hpt = roll(st.s_lvl, 8)       # monsters.c:77
    st.s_arm = mp['arm'] - lev_add
    st.s_dmg = mp['dmg']
    st.s_str = mp['str']
    st.s_exp = mp['exp'] + lev_add * 10 + exp_add(tp)
    tp.t_flags = mp['flags']
    if game.level > 29:
        tp.t_flags |= ISHASTE
    tp.t_turn = True
    tp.t_pack = []
    if game.is_wearing(R_AGGR):
        runto(game, cp)
    if type_ch == 'X':
        tp.t_disguise = rnd_thing(game)


def exp_add(tp):
    """monsters.c:95 -- experience to add for this monster's level/hp."""
    if tp.t_stats.s_lvl == 1:
        mod = tp.t_stats.s_maxhp // 8
    else:
        mod = tp.t_stats.s_maxhp // 6
    if tp.t_stats.s_lvl > 9:
        mod *= 20
    elif tp.t_stats.s_lvl > 6:
        mod *= 4
    return mod


def wanderer(game):
    """monsters.c:114 -- create a wandering monster and aim it at the player."""
    tp = Thing()
    cp = Coord()
    cnt = 0
    while True:
        # Avoid an endless loop when every room is full and the player's room
        # is unreachable.  monsters.c:123
        if cnt >= 500:
            return
        cnt += 1
        find_floor(game, None, cp, 0, True)
        if not (roomin(game, cp) is game.proom and game.moat(cp.y, cp.x) is None):
            break
    new_monster(game, tp, randmonster(game, True), cp)
    if on(game.player, SEEMONST):
        scr = game.screen
        scr.move(tp.t_pos.y, tp.t_pos.x)
        scr.standout()
        if not on(game.player, ISHALU):
            scr.addch(tp.t_type)
        else:
            scr.addch(chr(rnd(26) + ord('A')))
        scr.standend()
    runto(game, tp.t_pos)


def wake_monster(game, y, x):
    """monsters.c:152 -- what to do when the hero steps next to a monster."""
    tp = game.moat(y, x)
    if tp is None:
        return None

    ch = tp.t_type
    # Every time he sees a mean monster, it might start chasing him.
    if (not on(tp, ISRUN) and rnd(3) != 0 and on(tp, ISMEAN)
            and not on(tp, ISHELD) and not game.is_wearing(R_STEALTH)
            and not on(game.player, ISLEVIT)):
        tp.t_dest = game.hero
        tp.t_flags |= ISRUN

    # Medusa's gaze.  monsters.c:178
    if (ch == 'M' and not on(game.player, ISBLIND)
            and not on(game.player, ISHALU) and not on(tp, ISFOUND)
            and not on(tp, ISCANC) and on(tp, ISRUN)):
        rp = game.proom
        if ((rp is not None and not (rp.r_flags & ISDARK))
                or dist(y, x, game.hero.y, game.hero.x) < LAMPDIST):
            tp.t_flags |= ISFOUND
            if not save(game, VS_MAGIC):
                if on(game.player, ISHUH):
                    lengthen(game, unconfuse, spread(HUHDURATION))
                else:
                    fuse(game, unconfuse, 0, spread(HUHDURATION), AFTER)
                game.player.t_flags |= ISHUH
                mname = set_mname(game, tp)
                addmsg(game, "%s" % mname)
                if mname != "it":
                    addmsg(game, "'")
                msg(game, "s gaze has confused you")

    # Let greedy ones guard gold.  monsters.c:203
    if on(tp, ISGREED) and not on(tp, ISRUN):
        tp.t_flags |= ISRUN
        if game.proom is not None and game.proom.r_goldval:
            tp.t_dest = game.proom.r_gold
        else:
            tp.t_dest = game.hero
    return tp


def give_pack(game, tp):
    """monsters.c:218 -- give a pack to a monster if it deserves one."""
    if game.level >= game.max_level and rnd(100) < monster_info(tp.t_type)['carry']:
        tp.t_pack.append(new_thing(game))


def save_throw(which, tp):
    """monsters.c:228 -- see if a creature saves against something."""
    need = 14 + which - tp.t_stats.s_lvl // 2
    return roll(1, 20) >= need


def save(game, which):
    """monsters.c:241 -- see if the hero saves against various nasty things."""
    if which == VS_MAGIC:
        if game.is_ring(LEFT, R_PROTECT):
            which -= game.cur_ring[LEFT].o_arm
        if game.is_ring(RIGHT, R_PROTECT):
            which -= game.cur_ring[RIGHT].o_arm
    return save_throw(which, game.player)


# ---------------------------------------------------------------------------
# chase.c
# ---------------------------------------------------------------------------

def runners(game):
    """chase.c:25 -- make all the running monsters move."""
    # iterate over a snapshot: a monster can die (and be removed) mid-loop
    for tp in list(game.mlist):
        if tp.t_dead or tp not in game.mlist:
            continue
        if not on(tp, ISHELD) and on(tp, ISRUN):
            orig_pos = tp.t_pos.copy()
            wastarget = on(tp, ISTARGET)
            if move_monst(game, tp) == -1:
                continue
            if on(tp, ISFLY) and dist_cp(game.hero, tp.t_pos) >= 3:
                move_monst(game, tp)
            if wastarget and orig_pos != tp.t_pos:
                tp.t_flags &= ~ISTARGET
                game.to_death = False
    if game.has_hit:
        endmsg(game)
        game.has_hit = False


def move_monst(game, tp):
    """chase.c:60 -- execute a single turn of running for a monster."""
    if not on(tp, ISSLOW) or tp.t_turn:
        if do_chase(game, tp) == -1:
            return -1
    if on(tp, ISHASTE):
        if do_chase(game, tp) == -1:
            return -1
    tp.t_turn = not tp.t_turn
    return 0


def relocate(game, th, new_loc):
    """chase.c:77 -- move the monster, updating all the relevant state."""
    scr = game.screen
    if new_loc != th.t_pos:
        scr.mvaddch(th.t_pos.y, th.t_pos.x, th.t_oldch)
        th.t_room = roomin(game, new_loc)
        set_oldch(game, th, new_loc)
        oroom = th.t_room
        game.set_moat(th.t_pos.y, th.t_pos.x, None)
        if oroom is not th.t_room:
            th.t_dest = find_dest(game, th)
        th.t_pos.set(new_loc)
        game.set_moat(new_loc.y, new_loc.x, th)
    scr.move(new_loc.y, new_loc.x)
    if see_monst(game, th):
        scr.addch(th.t_disguise)
    elif on(game.player, SEEMONST):
        scr.standout()
        scr.addch(th.t_type)
        scr.standend()


def do_chase(game, th):
    """chase.c:110 -- make one thing chase another."""
    mindist = 32767
    stoprun = False
    this = Coord()

    rer = th.t_room                     # room of chaser
    if on(th, ISGREED) and rer is not None and rer.r_goldval == 0:
        th.t_dest = game.hero
    if th.t_dest is game.hero:
        ree = game.proom
    else:
        ree = roomin(game, th.t_dest)

    # We don't count doors as inside rooms for this routine.
    door_here = (game.chat(th.t_pos.y, th.t_pos.x) == DOOR)

    # the C uses a goto to re-run this block once, after stepping out of a door
    while True:
        if rer is not ree:
            if rer is not None:
                for i in range(rer.r_nexits):
                    cp = rer.r_exit[i]
                    curdist = dist_cp(th.t_dest, cp)
                    if curdist < mindist:
                        this.set(cp)
                        mindist = curdist
            if door_here:
                rer = game.passages[game.flat(th.t_pos.y, th.t_pos.x) & F_PNUM]
                door_here = False
                continue                # goto over
        else:
            this.set(th.t_dest)
            # Dragons breathe at the hero on a straight line.  chase.c:148
            if (th.t_type == 'D'
                    and (th.t_pos.y == game.hero.y or th.t_pos.x == game.hero.x
                         or abs(th.t_pos.y - game.hero.y) == abs(th.t_pos.x - game.hero.x))
                    and dist_cp(th.t_pos, game.hero) <= BOLT_LENGTH * BOLT_LENGTH
                    and not on(th, ISCANC) and rnd(DRAGONSHOT) == 0):
                game.delta.y = sign(game.hero.y - th.t_pos.y)
                game.delta.x = sign(game.hero.x - th.t_pos.x)
                if game.has_hit:
                    endmsg(game)
                fire_bolt(game, th.t_pos, game.delta, "flame")
                game.running = False
                game.count = 0
                game.quiet = 0
                if game.to_death and not on(th, ISTARGET):
                    game.to_death = False
                    game.kamikaze = False
                return 0
        break

    ch_ret = Coord()
    keep_chasing = chase(game, th, this, ch_ret)
    if not keep_chasing:
        if this == game.hero:
            return attack(game, th)
        elif this == th.t_dest:
            for obj in list(game.lvl_obj):
                if th.t_dest is obj.o_pos:
                    game.lvl_obj.remove(obj)
                    th.t_pack.append(obj)
                    game.set_chat(obj.o_pos.y, obj.o_pos.x,
                                  PASSAGE if (th.t_room.r_flags & ISGONE) else FLOOR)
                    th.t_dest = find_dest(game, th)
                    break
            if th.t_type != 'F':
                stoprun = True
    else:
        if th.t_type == 'F':
            return 0

    relocate(game, th, ch_ret)
    if stoprun and th.t_pos == th.t_dest:
        th.t_flags &= ~ISRUN
    return 0


def set_oldch(game, tp, cp):
    """chase.c:229 -- set the oldch character for the monster."""
    if tp.t_pos == cp:
        return
    sch = tp.t_oldch
    tp.t_oldch = game.screen.mvinch(cp.y, cp.x)
    if not on(game.player, ISBLIND):
        if ((sch == FLOOR or tp.t_oldch == FLOOR)
                and tp.t_room is not None and (tp.t_room.r_flags & ISDARK)):
            tp.t_oldch = ' '
        elif dist_cp(cp, game.hero) <= LAMPDIST and game.see_floor:
            tp.t_oldch = game.chat(cp.y, cp.x)


def see_monst(game, mp):
    """chase.c:252 -- can the hero see this monster?"""
    if on(game.player, ISBLIND):
        return False
    if on(mp, ISINVIS) and not on(game.player, CANSEE):
        return False
    y = mp.t_pos.y
    x = mp.t_pos.x
    if dist(y, x, game.hero.y, game.hero.x) < LAMPDIST:
        if (y != game.hero.y and x != game.hero.x
                and not step_ok(game.chat(y, game.hero.x))
                and not step_ok(game.chat(game.hero.y, x))):
            return False
        return True
    if mp.t_room is not game.proom:
        return False
    return not (mp.t_room.r_flags & ISDARK)


def runto(game, runner):
    """chase.c:281 -- set a monster running after the hero."""
    tp = game.moat(runner.y, runner.x)
    if tp is None:
        return
    tp.t_flags |= ISRUN
    tp.t_flags &= ~ISHELD
    tp.t_dest = find_dest(game, tp)


def chase(game, tp, ee, ch_ret):
    """chase.c:308 -- find the spot to move closer to the chasee.

    Returns True to keep chasing, False on reaching the goal.  ch_ret is the
    C's static `ch_ret`, passed explicitly here.
    """
    er = tp.t_pos
    plcnt = 1

    # Confused things move randomly.  Invisible stalkers are slightly confused
    # all the time, and bats are quite confused all the time.  chase.c:322
    if ((on(tp, ISHUH) and rnd(5) != 0) or (tp.t_type == 'P' and rnd(5) == 0)
            or (tp.t_type == 'B' and rnd(2) == 0)):
        ch_ret.set(rndmove(game, tp))
        curdist = dist_cp(ch_ret, ee)
        if rnd(20) == 0:
            tp.t_flags &= ~ISHUH
    else:
        curdist = dist_cp(er, ee)
        ch_ret.set(er)

        ey = er.y + 1
        if ey >= NUMLINES - 1:
            ey = NUMLINES - 2
        ex = er.x + 1
        if ex >= NUMCOLS:
            ex = NUMCOLS - 1

        tryp = Coord()
        for x in range(er.x - 1, ex + 1):
            if x < 0:
                continue
            tryp.x = x
            for y in range(er.y - 1, ey + 1):
                tryp.y = y
                if not diag_ok(game, er, tryp):
                    continue
                ch = game.winat(y, x)
                if not step_ok(ch):
                    continue
                # A scroll might be a scare monster scroll.  chase.c:365
                if ch == SCROLL:
                    found = None
                    for obj in game.lvl_obj:
                        if y == obj.o_pos.y and x == obj.o_pos.x:
                            found = obj
                            break
                    if found is not None and found.o_which == S_SCARE:
                        continue
                # It can also be a Xeroc, which we shouldn't step on.
                mobj = game.moat(y, x)
                if mobj is not None and mobj.t_type == 'X':
                    continue
                thisdist = dist(y, x, ee.y, ee.x)
                if thisdist < curdist:
                    plcnt = 1
                    ch_ret.set(tryp)
                    curdist = thisdist
                elif thisdist == curdist:
                    plcnt += 1
                    if rnd(plcnt) == 0:
                        ch_ret.set(tryp)
                        curdist = thisdist

    return curdist != 0 and ch_ret != game.hero


def roomin(game, cp):
    """chase.c:426 -- find what room some coordinates are in."""
    fl = game.flat(cp.y, cp.x)
    if fl & F_PASS:
        return game.passages[fl & F_PNUM]
    for rp in game.rooms:
        if (cp.x <= rp.r_pos.x + rp.r_max.x and rp.r_pos.x <= cp.x
                and cp.y <= rp.r_pos.y + rp.r_max.y and rp.r_pos.y <= cp.y):
            return rp
    msg(game, "in some bizarre place (%d, %d)" % (cp.y, cp.x))
    return None


def diag_ok(game, sp, ep):
    """chase.c:452 -- check that a diagonal move is legal."""
    if ep.x < 0 or ep.x >= NUMCOLS or ep.y <= 0 or ep.y >= NUMLINES - 1:
        return False
    if ep.x == sp.x or ep.y == sp.y:
        return True
    return (step_ok(game.chat(ep.y, sp.x)) and step_ok(game.chat(sp.y, ep.x)))


def cansee(game, y, x):
    """chase.c:467 -- can the hero see this coordinate?"""
    if on(game.player, ISBLIND):
        return False
    if dist(y, x, game.hero.y, game.hero.x) < LAMPDIST:
        if game.flat(y, x) & F_PASS:
            if (y != game.hero.y and x != game.hero.x
                    and not step_ok(game.chat(y, game.hero.x))
                    and not step_ok(game.chat(game.hero.y, x))):
                return False
        return True
    tp = Coord(x, y)
    rer = roomin(game, tp)
    return rer is game.proom and rer is not None and not (rer.r_flags & ISDARK)


def find_dest(game, tp):
    """chase.c:471 -- find the proper destination for the monster.

    PORT NOTE: the C reuses its own parameter `tp` as the mlist walker in the
    inner loop.  When an object is already claimed, the outer loop therefore
    continues with `tp` pointing at the CLAIMING monster, so every later
    `tp->t_room` test compares against the wrong room.  That is a real bug in
    5.4.5, but it changes both which object a treasure-seeker picks and how
    many rnd(100) draws are consumed, so it is reproduced rather than fixed.
    """
    prob = monster_info(tp.t_type)['carry']
    if prob <= 0 or tp.t_room is game.proom or see_monst(game, tp):
        return game.hero
    for obj in game.lvl_obj:
        if obj.o_type == SCROLL and obj.o_which == S_SCARE:
            continue
        if roomin(game, obj.o_pos) is tp.t_room and rnd(100) < prob:
            claimer = None
            for other in game.mlist:
                if other.t_dest is obj.o_pos:
                    claimer = other
                    break
            if claimer is None:
                return obj.o_pos
            tp = claimer                # the C's parameter clobber
    return game.hero


# ---------------------------------------------------------------------------
# Combat.  Ported from fight.c
# ---------------------------------------------------------------------------

H_NAMES = (                     # fight.c:21  strings for hitting
    " scored an excellent hit on ",
    " hit ",
    " have injured ",
    " swing and hit ",
    " scored an excellent hit on ",
    " hit ",
    " has injured ",
    " swings and hits ",
)

M_NAMES = (                     # fight.c:32  strings for missing
    " miss",
    " swing and miss",
    " barely miss",
    " don't hit",
    " misses",
    " swings and misses",
    " barely misses",
    " doesn't hit",
)


def fight(game, mp, weap, thrown):
    """fight.c:62 -- the player attacks the monster."""
    tp = game.moat(mp.y, mp.x)
    if tp is None:
        return False

    # Since we are fighting, things are not quiet, so no healing takes place.
    game.count = 0
    game.quiet = 0
    runto(game, mp)

    # Let him know it was really a xeroc (if it was one).  fight.c:87
    if tp.t_type == 'X' and tp.t_disguise != 'X' and not on(game.player, ISBLIND):
        tp.t_disguise = 'X'
        if on(game.player, ISHALU):
            game.screen.mvaddch(tp.t_pos.y, tp.t_pos.x, chr(rnd(26) + ord('A')))
        msg(game, choose_str(game, "heavy!  That's a nasty critter!",
                             "wait!  That's a xeroc!"))
        if not thrown:
            return False

    mname = set_mname(game, tp)
    did_hit = False
    game.has_hit = (game.terse and not game.to_death)
    if roll_em(game, game.player, tp, weap, thrown):
        did_hit = False
        if thrown:
            thunk(game, weap, mname, game.terse)
        else:
            hit(game, None, mname, game.terse)
        if on(game.player, CANHUH):
            did_hit = True
            tp.t_flags |= ISHUH
            game.player.t_flags &= ~CANHUH
            endmsg(game)
            game.has_hit = False
            msg(game, "your hands stop glowing %s" % pick_color(game, "red"))
        if tp.t_stats.s_hpt <= 0:
            killed(game, tp, True)
        elif did_hit and not on(game.player, ISBLIND):
            msg(game, "%s appears confused" % mname)
        did_hit = True
    else:
        if thrown:
            bounce(game, weap, mname, game.terse)
        else:
            miss(game, None, mname, game.terse)
    return did_hit


def attack(game, mp):
    """fight.c:136 -- the monster attacks the player."""
    game.running = False
    game.count = 0
    game.quiet = 0
    if game.to_death and not on(mp, ISTARGET):
        game.to_death = False
        game.kamikaze = False
    if mp.t_type == 'X' and mp.t_disguise != 'X' and not on(game.player, ISBLIND):
        mp.t_disguise = 'X'
        if on(game.player, ISHALU):
            game.screen.mvaddch(mp.t_pos.y, mp.t_pos.x, chr(rnd(26) + ord('A')))

    mname = set_mname(game, mp)
    oldhp = game.pstats.s_hpt
    removed = False

    if roll_em(game, mp, game.player, None, False):
        if mp.t_type != 'I':
            if game.has_hit:
                addmsg(game, ".  ")
            hit(game, mname, None, False)
        else:
            if game.has_hit:
                endmsg(game)
        game.has_hit = False
        if game.pstats.s_hpt <= 0:
            death(game, mp.t_type)
            return 0
        elif not game.kamikaze:
            oldhp -= game.pstats.s_hpt
            if oldhp > game.max_hit:
                game.max_hit = oldhp
            if game.pstats.s_hpt <= game.max_hit:
                game.to_death = False

        if not on(mp, ISCANC):
            t = mp.t_type
            if t == 'A':
                # If an aquator hits, you can lose armor class.  fight.c:196
                rust_armor(game, game.cur_armor)
            elif t == 'I':
                # The ice monster freezes you.  fight.c:201
                game.player.t_flags &= ~ISRUN
                if not game.no_command:
                    addmsg(game, "you are frozen")
                    if not game.terse:
                        addmsg(game, " by the %s" % mname)
                    endmsg(game)
                game.no_command += rnd(2) + 2
                if game.no_command > BORE_LEVEL:
                    death(game, 'h')
                    return 0
            elif t == 'R':
                # Rattlesnakes have poisonous bites.  fight.c:215
                if not save(game, VS_POISON):
                    if not game.is_wearing(R_SUSTSTR):
                        chg_str(game, -1)
                        if not game.terse:
                            msg(game, "you feel a bite in your leg and now feel weaker")
                        else:
                            msg(game, "a bite has weakened you")
                    elif not game.to_death:
                        if not game.terse:
                            msg(game, "a bite momentarily weakens you")
                        else:
                            msg(game, "bite has no effect")
            elif t in ('W', 'V'):
                # Wraiths drain levels; vampires steal max hp.  fight.c:236
                if rnd(100) < (15 if t == 'W' else 30):
                    if t == 'W':
                        if game.pstats.s_exp == 0:
                            death(game, 'W')        # all levels gone
                            return 0
                        game.pstats.s_lvl -= 1
                        if game.pstats.s_lvl == 0:
                            game.pstats.s_exp = 0
                            game.pstats.s_lvl = 1
                        else:
                            game.pstats.s_exp = E_LEVELS[game.pstats.s_lvl - 1] + 1
                        fewer = roll(1, 10)
                    else:
                        fewer = roll(1, 3)
                    game.pstats.s_hpt -= fewer
                    game.pstats.s_maxhp -= fewer
                    if game.pstats.s_hpt <= 0:
                        game.pstats.s_hpt = 1
                    if game.pstats.s_maxhp <= 0:
                        death(game, t)
                        return 0
                    msg(game, "you suddenly feel weaker")
            elif t == 'F':
                # Venus flytrap stops the poor guy from moving.  fight.c:268
                game.player.t_flags |= ISHELD
                game.vf_hit += 1
                MONSTERS[ord('F') - ord('A')]['dmg'] = "%dx1" % game.vf_hit
                game.pstats.s_hpt -= 1
                if game.pstats.s_hpt <= 0:
                    death(game, 'F')
                    return 0
            elif t == 'L':
                # Leprechaun steals some gold.  fight.c:277
                lastpurse = game.purse
                game.purse -= game.goldcalc()
                if not save(game, VS_MAGIC):
                    game.purse -= (game.goldcalc() + game.goldcalc()
                                   + game.goldcalc() + game.goldcalc())
                if game.purse < 0:
                    game.purse = 0
                remove_mon(game, mp.t_pos, mp, False)
                removed = True
                if game.purse != lastpurse:
                    msg(game, "your purse feels lighter")
            elif t == 'N':
                # Nymphs steal a magic item.  fight.c:295
                steal = None
                nobj = 0
                for obj in game.pack:
                    if (obj is not game.cur_armor and obj is not game.cur_weapon
                            and obj is not game.cur_ring[LEFT]
                            and obj is not game.cur_ring[RIGHT]
                            and is_magic(obj)):
                        nobj += 1
                        if rnd(nobj) == 0:
                            steal = obj
                if steal is not None:
                    remove_mon(game, mp.t_pos,
                               game.moat(mp.t_pos.y, mp.t_pos.x), False)
                    removed = True
                    steal = leave_pack(game, steal, True, False)
                    msg(game, "she stole %s!" % inv_name(game, steal, True))
    elif mp.t_type != 'I':
        if game.has_hit:
            addmsg(game, ".  ")
            game.has_hit = False
        if mp.t_type == 'F':
            game.pstats.s_hpt -= game.vf_hit
            if game.pstats.s_hpt <= 0:
                death(game, mp.t_type)
                return 0
        miss(game, mname, None, False)

    game.count = 0
    return -1 if removed else 0


def set_mname(game, tp):
    """fight.c:380 -- the monster name for the given monster."""
    if not see_monst(game, tp) and not on(game.player, SEEMONST):
        return "it" if game.terse else "something"
    if on(game.player, ISHALU):
        ch = game.screen.inch(tp.t_pos.y, tp.t_pos.x)
        if not isupper_ch(ch):
            idx = rnd(26)
        else:
            idx = ord(ch) - ord('A')
        mname = MONSTERS[idx]['name']
    else:
        mname = monster_info(tp.t_type)['name']
    return "the " + mname


def swing(at_lvl, op_arm, wplus):
    """fight.c:409 -- returns true if the swing hits."""
    res = rnd(20)
    need = (20 - at_lvl) - op_arm
    return (res + wplus) >= need


def roll_em(game, thatt, thdef, weap, hurl):
    """fight.c:421 -- roll several attacks."""
    att = thatt.t_stats
    de = thdef.t_stats
    did_hit = False

    if weap is None:
        cp = att.s_dmg
        dplus = 0
        hplus = 0
    else:
        hplus = weap.o_hplus
        dplus = weap.o_dplus
        if weap is game.cur_weapon:
            if game.is_ring(LEFT, R_ADDDAM):
                dplus += game.cur_ring[LEFT].o_arm
            elif game.is_ring(LEFT, R_ADDHIT):
                hplus += game.cur_ring[LEFT].o_arm
            if game.is_ring(RIGHT, R_ADDDAM):
                dplus += game.cur_ring[RIGHT].o_arm
            elif game.is_ring(RIGHT, R_ADDHIT):
                hplus += game.cur_ring[RIGHT].o_arm
        cp = weap.o_damage
        if hurl:
            if ((weap.o_flags & ISMISL) and game.cur_weapon is not None
                    and game.cur_weapon.o_which == weap.o_launch):
                cp = weap.o_hurldmg
                hplus += game.cur_weapon.o_hplus
                dplus += game.cur_weapon.o_dplus
            elif weap.o_launch < 0:
                cp = weap.o_hurldmg

    # A defender that is not running (asleep or held) is +4 to hit.  fight.c:466
    if not on(thdef, ISRUN):
        hplus += 4

    def_arm = de.s_arm
    if thdef is game.player:
        if game.cur_armor is not None:
            def_arm = game.cur_armor.o_arm
        if game.is_ring(LEFT, R_PROTECT):
            def_arm -= game.cur_ring[LEFT].o_arm
        if game.is_ring(RIGHT, R_PROTECT):
            def_arm -= game.cur_ring[RIGHT].o_arm

    s_idx = max(0, min(31, att.s_str))
    for ndice, nsides in parse_dice(cp):
        if swing(att.s_lvl, def_arm, hplus + STR_PLUS[s_idx]):
            proll = roll(ndice, nsides)
            damage = dplus + proll + ADD_DAM[s_idx]
            de.s_hpt -= max(0, damage)
            did_hit = True
    return did_hit


def thunk(game, weap, mname, noend):
    """fight.c:540 -- a missile hits a monster."""
    if game.to_death:
        return
    if weap.o_type == WEAPON:
        addmsg(game, "the %s hits " % game.weap_names[weap.o_which])
    else:
        addmsg(game, "you hit ")
    addmsg(game, "%s" % mname)
    if not noend:
        endmsg(game)


def hit(game, er, ee, noend):
    """fight.c:558 -- print a message to indicate a successful hit."""
    if game.to_death:
        return
    addmsg(game, prname(er, True))
    if game.terse:
        s = " hit"
    else:
        i = rnd(4)
        if er is not None:
            i += 4
        s = H_NAMES[i]
    addmsg(game, s)
    if not game.terse:
        addmsg(game, prname(ee, False))
    if not noend:
        endmsg(game)


def miss(game, er, ee, noend):
    """fight.c:586 -- print a message to indicate a poor swing."""
    if game.to_death:
        return
    addmsg(game, prname(er, True))
    i = 0 if game.terse else rnd(4)
    if er is not None:
        i += 4
    addmsg(game, M_NAMES[i])
    if not game.terse:
        addmsg(game, " %s" % prname(ee, False))
    if not noend:
        endmsg(game)


def bounce(game, weap, mname, noend):
    """fight.c:609 -- a missile misses a monster."""
    if game.to_death:
        return
    if weap.o_type == WEAPON:
        addmsg(game, "the %s misses " % game.weap_names[weap.o_which])
    else:
        addmsg(game, "you missed ")
    addmsg(game, mname)
    if not noend:
        endmsg(game)


def remove_mon(game, mp, tp, waskill):
    """fight.c:626 -- remove a monster from the screen."""
    if tp is None:
        return
    for obj in list(tp.t_pack):
        obj.o_pos = tp.t_pos.copy()
        tp.t_pack.remove(obj)
        if waskill:
            fall(game, obj, False)
    game.set_moat(mp.y, mp.x, None)
    game.screen.mvaddch(mp.y, mp.x, tp.t_oldch)
    if tp in game.mlist:
        game.mlist.remove(tp)
    tp.t_dead = True
    if on(tp, ISTARGET):
        game.kamikaze = False
        game.to_death = False


def killed(game, tp, pr):
    """fight.c:657 -- called to put a monster to death."""
    game.pstats.s_exp += tp.t_stats.s_exp

    if tp.t_type == 'F':
        # un-hold the player and reset the flytrap's accumulated damage
        game.player.t_flags &= ~ISHELD
        game.vf_hit = 0
        MONSTERS[ord('F') - ord('A')]['dmg'] = "000x0"
    elif tp.t_type == 'L':
        # Leprechaun drops gold.  fight.c:672
        if (tp.t_room is not None
                and fallpos(game, tp.t_pos, tp.t_room.r_gold)
                and game.level >= game.max_level):
            gold = Obj()
            gold.o_type = GOLD
            gold.o_goldval = game.goldcalc()
            if save(game, VS_MAGIC):
                gold.o_goldval += (game.goldcalc() + game.goldcalc()
                                   + game.goldcalc() + game.goldcalc())
            tp.t_pack.append(gold)

    mname = set_mname(game, tp)
    remove_mon(game, tp.t_pos, tp, True)
    if pr:
        if game.has_hit:
            addmsg(game, ".  Defeated ")
            game.has_hit = False
        else:
            if not game.terse:
                addmsg(game, "you have ")
            addmsg(game, "defeated ")
        msg(game, mname)
    check_level(game)


# ---------------------------------------------------------------------------
# Miscellaneous routines.  Ported from misc.c
# ---------------------------------------------------------------------------

THING_LIST = (POTION, SCROLL, RING, STICK, FOOD, WEAPON, ARMOR, STAIRS,
              GOLD, AMULET)                                  # misc.c:600


def look(game, wakeup):
    """misc.c:22 -- a quick glance all around the player.

    This is Rogue's entire field-of-view model: the eight cells around the
    hero, plus whatever a lit room already revealed on entry.  There is no
    raycasting anywhere in the original and none is added here.
    """
    scr = game.screen
    passcount = 0
    rp = game.proom
    sumhero = diffhero = 0

    if game.oldpos != game.hero:
        if game.oldrp is not None:
            erase_lamp(game, game.oldpos, game.oldrp)
        game.oldpos.set(game.hero)
        game.oldrp = rp

    ey = game.hero.y + 1
    ex = game.hero.x + 1
    sx = game.hero.x - 1
    sy = game.hero.y - 1
    if game.door_stop and not game.firstmove and game.running:
        sumhero = game.hero.y + game.hero.x
        diffhero = game.hero.y - game.hero.x

    pp = game.place(game.hero.y, game.hero.x)
    pch = pp.p_ch
    pfl = pp.p_flags

    for y in range(sy, ey + 1):
        if not (0 < y < NUMLINES - 1):
            continue
        for x in range(sx, ex + 1):
            if x < 0 or x >= NUMCOLS:
                continue
            if not on(game.player, ISBLIND):
                if y == game.hero.y and x == game.hero.x:
                    continue

            pp = game.place(y, x)
            ch = pp.p_ch
            if ch == ' ':
                continue
            fp = pp.p_flags
            if pch != DOOR and ch != DOOR:
                if (pfl & F_PASS) != (fp & F_PASS):
                    continue
            if ((fp & F_PASS) or ch == DOOR) and ((pfl & F_PASS) or pch == DOOR):
                if (game.hero.x != x and game.hero.y != y
                        and not step_ok(game.chat(y, game.hero.x))
                        and not step_ok(game.chat(game.hero.y, x))):
                    continue

            tp = pp.p_monst
            if tp is None:
                ch = trip_ch(game, y, x, ch)
            else:
                if on(game.player, SEEMONST) and on(tp, ISINVIS):
                    if game.door_stop and not game.firstmove:
                        game.running = False
                    continue
                if wakeup:
                    wake_monster(game, y, x)
                if see_monst(game, tp):
                    if on(game.player, ISHALU):
                        ch = chr(rnd(26) + ord('A'))
                    else:
                        ch = tp.t_disguise

            if on(game.player, ISBLIND) and (y != game.hero.y or x != game.hero.x):
                continue

            scr.move(y, x)
            if (rp is not None and (rp.r_flags & ISDARK)
                    and not game.see_floor and ch == FLOOR):
                ch = ' '
            if tp is not None or ch != scr.inch():
                scr.addch(ch)

            if game.door_stop and not game.firstmove and game.running:
                rc = game.runch
                if rc == 'h' and x == ex:
                    continue
                elif rc == 'j' and y == sy:
                    continue
                elif rc == 'k' and y == ey:
                    continue
                elif rc == 'l' and x == sx:
                    continue
                elif rc == 'y' and (y + x) - sumhero >= 1:
                    continue
                elif rc == 'u' and (y - x) - diffhero >= 1:
                    continue
                elif rc == 'n' and (y + x) - sumhero <= -1:
                    continue
                elif rc == 'b' and (y - x) - diffhero <= -1:
                    continue

                if ch == DOOR:
                    if x == game.hero.x or y == game.hero.y:
                        game.running = False
                elif ch == PASSAGE:
                    if x == game.hero.x or y == game.hero.y:
                        passcount += 1
                elif ch in (FLOOR, VWALL, HWALL, ' '):
                    pass
                else:
                    game.running = False

    if game.door_stop and not game.firstmove and passcount > 1:
        game.running = False
    if not game.running or not game.jump:
        scr.mvaddch(game.hero.y, game.hero.x, PLAYER)


def trip_ch(game, y, x, ch):
    """misc.c:186 -- the character for this space, accounting for tripping."""
    if on(game.player, ISHALU) and game.after:
        if ch in (FLOOR, ' ', PASSAGE, HWALL, VWALL, DOOR, TRAP):
            return ch
        if y != game.stairs.y or x != game.stairs.x or not game.seenstairs:
            ch = rnd_thing(game)
    return ch


def erase_lamp(game, pos, rp):
    """misc.c:214 -- erase the area shown by a lamp in a dark room."""
    if not (game.see_floor and (rp.r_flags & (ISGONE | ISDARK)) == ISDARK
            and not on(game.player, ISBLIND)):
        return
    scr = game.screen
    ey = pos.y + 1
    ex = pos.x + 1
    sy = pos.y - 1
    for x in range(pos.x - 1, ex + 1):
        for y in range(sy, ey + 1):
            if y == game.hero.y and x == game.hero.x:
                continue
            if not game.in_bounds(y, x):
                continue
            scr.move(y, x)
            if scr.inch() == FLOOR:
                scr.addch(' ')


def show_floor(game):
    """misc.c:243 -- should we show the floor in her room at this time?"""
    if (game.proom is not None
            and (game.proom.r_flags & (ISGONE | ISDARK)) == ISDARK
            and not on(game.player, ISBLIND)):
        return game.see_floor
    return True


def find_obj(game, y, x):
    """misc.c:257 -- find the unclaimed object at y, x."""
    for obj in game.lvl_obj:
        if obj.o_pos.y == y and obj.o_pos.x == x:
            return obj
    return None


def eat(game, obj):
    """misc.c:280 -- she wants to eat something, so let her try."""
    if obj is None:
        return
    if obj.o_type != FOOD:
        if not game.terse:
            msg(game, "ugh, you would get ill if you ate that")
        else:
            msg(game, "that's Inedible!")
        return
    if game.food_left < 0:
        game.food_left = 0
    game.food_left += HUNGERTIME - 200 + rnd(400)
    if game.food_left > STOMACHSIZE:
        game.food_left = STOMACHSIZE
    game.hungry_state = F_OKAY
    if obj is game.cur_weapon:
        game.cur_weapon = None
    if obj.o_which == 1:
        msg(game, "my, that was a yummy %s" % FRUIT)
    elif rnd(100) > 70:
        game.pstats.s_exp += 1
        msg(game, "%s, this food tastes awful"
            % choose_str(game, "bummer", "yuk"))
        check_level(game)
    else:
        msg(game, "%s, that tasted good" % choose_str(game, "oh, wow", "yum"))
    leave_pack(game, obj, False, False)


def check_level(game):
    """misc.c:318 -- check to see if the guy has gone up a level.

    PORT NOTE: E_LEVELS carries the 20 real thresholds; the C array has a
    trailing 0 sentinel and the scan stops there, so the level caps at 21.
    Nothing doubles past the end of the table.
    """
    i = 0
    while i < len(E_LEVELS):
        if E_LEVELS[i] > game.pstats.s_exp:
            break
        i += 1
    i += 1
    olevel = game.pstats.s_lvl
    game.pstats.s_lvl = i
    if i > olevel:
        add = roll(i - olevel, 10)
        game.pstats.s_maxhp += add
        game.pstats.s_hpt += add
        msg(game, "welcome to level %d" % i)


def raise_level(game):
    """potions.c:294 -- bump experience to the next level threshold.

    The C's e_levels[] has a trailing 0 sentinel, so at the level cap of 21
    it reads that 0 and sets experience to 1.  E_LEVELS here holds only the
    20 real thresholds, so the sentinel has to be supplied or this indexes
    off the end and raises IndexError.
    """
    i = game.pstats.s_lvl - 1
    game.pstats.s_exp = (E_LEVELS[i] if i < len(E_LEVELS) else 0) + 1
    check_level(game)


def chg_str(game, amt):
    """misc.c:343 -- modify the player's strength, tracking the maximum."""
    if amt == 0:
        return
    game.pstats.s_str = add_str(game.pstats.s_str, amt)
    comp = game.pstats.s_str
    if game.is_ring(LEFT, R_ADDSTR):
        comp = add_str(comp, -game.cur_ring[LEFT].o_arm)
    if game.is_ring(RIGHT, R_ADDSTR):
        comp = add_str(comp, -game.cur_ring[RIGHT].o_arm)
    if comp > game.max_stats.s_str:
        game.max_stats.s_str = comp


def add_str(sp, amt):
    """misc.c:365 -- the actual add, with bounds.  Returns the new value."""
    sp += amt
    if sp < 3:
        return 3
    if sp > 31:
        return 31
    return sp


def add_haste(game, potion):
    """misc.c:378 -- add a haste to the player."""
    if on(game.player, ISHASTE):
        game.no_command += rnd(8)
        game.player.t_flags &= ~(ISRUN | ISHASTE)
        extinguish(game, nohaste)
        msg(game, "you faint from exhaustion")
        return False
    game.player.t_flags |= ISHASTE
    if potion:
        fuse(game, nohaste, 0, rnd(4) + 4, AFTER)
    return True


def aggravate(game):
    """misc.c:401 -- aggravate all the monsters on this level."""
    for mp in game.mlist:
        runto(game, mp.t_pos)


def is_current(game, obj):
    """misc.c:467 -- see if the object is one of the currently used items."""
    if obj is None:
        return False
    if (obj is game.cur_armor or obj is game.cur_weapon
            or obj is game.cur_ring[LEFT] or obj is game.cur_ring[RIGHT]):
        if not game.terse:
            addmsg(game, "That's already ")
        msg(game, "in use")
        return True
    return False


def rnd_thing(game):
    """misc.c:595 -- pick a random thing appropriate for this level."""
    if game.level >= AMULETLEVEL:
        i = rnd(len(THING_LIST))
    else:
        i = rnd(len(THING_LIST) - 1)
    return THING_LIST[i]


def fallpos(game, pos, newpos):
    """weapons.c:281 -- pick a random position around the given coordinates."""
    cnt = 0
    for y in range(pos.y - 1, pos.y + 2):
        for x in range(pos.x - 1, pos.x + 2):
            # check the spot is empty; if it is, put the object there
            if y == game.hero.y and x == game.hero.x:
                continue
            if not game.in_bounds(y, x):
                continue
            ch = game.chat(y, x)
            if ch == FLOOR or ch == PASSAGE:
                cnt += 1
                if rnd(cnt) == 0:
                    newpos.y = y
                    newpos.x = x
    return cnt != 0


# ---------------------------------------------------------------------------
# Items: creation, naming, and the pack.
# Ported from things.c, pack.c, init.c, weapons.c, armor.c and sticks.c
# ---------------------------------------------------------------------------

FRUIT = "slime-mold"            # options.c default
MAXNAME = 40                    # init.c:259  max characters in a scroll name


# ---------------------------------------------------------------------------
# Per-game randomised appearances.  init.c
# ---------------------------------------------------------------------------

def init_colors(game):
    """init.c:236 -- assign a random colour to each potion."""
    used = [False] * len(RAINBOW)
    game.p_colors = []
    for _ in range(MAXPOTIONS):
        while True:
            j = rnd(len(RAINBOW))
            if not used[j]:
                break
        used[j] = True
        game.p_colors.append(RAINBOW[j])


def init_names(game):
    """init.c:262 -- generate the titles of the various scrolls."""
    game.s_names = []
    for _ in range(MAXSCROLLS):
        buf = []
        length = 0
        nwords = rnd(3) + 2
        while nwords:
            nwords -= 1
            nsyl = rnd(3) + 1
            while nsyl:
                nsyl -= 1
                sp = SYLLABLES[rnd(len(SYLLABLES))]
                if length + len(sp) > MAXNAME:
                    break
                buf.append(sp)
                length += len(sp)
            buf.append(' ')
            length += 1
        game.s_names.append(''.join(buf).strip())


def init_stones(game):
    """init.c:299 -- assign a gem to each ring and add its value to the worth."""
    used = [False] * len(STONES)
    game.r_stones = []
    for i in range(MAXRINGS):
        while True:
            j = rnd(len(STONES))
            if not used[j]:
                break
        used[j] = True
        game.r_stones.append(STONES[j]['name'])
        game.ring_info[i].oi_worth += STONES[j]['value']


def init_materials(game):
    """init.c:321 -- pick wand/staff materials for this game."""
    used = [False] * len(WOOD)
    metused = [False] * len(METAL)
    game.ws_type = []
    game.ws_made = []
    for _ in range(MAXSTICKS):
        while True:
            if rnd(2) == 0:
                j = rnd(len(METAL))
                if not metused[j]:
                    game.ws_type.append("wand")
                    game.ws_made.append(METAL[j])
                    metused[j] = True
                    break
            else:
                j = rnd(len(WOOD))
                if not used[j]:
                    game.ws_type.append("staff")
                    game.ws_made.append(WOOD[j])
                    used[j] = True
                    break


def sumprobs(info):
    """init.c:383 -- rewrite raw probabilities into a running total.

    PORT NOTE: the tables are transcribed with the C's RAW percentages (each
    summing to 100).  The C mutates them in place at startup into cumulative
    form because pick_one() compares rnd(100) against oi_prob directly.  Same
    thing here, done once per game on the per-game ObjInfo copies.
    """
    for i in range(1, len(info)):
        info[i].oi_prob += info[i - 1].oi_prob


def init_probs(game):
    """init.c:405"""
    game.things = [ObjInfo(t['name'], t['prob'], 0) for t in THINGS]
    game.pot_info = [ObjInfo(r['name'], r['prob'], r['worth']) for r in POT_INFO]
    game.scr_info = [ObjInfo(r['name'], r['prob'], r['worth']) for r in SCR_INFO]
    game.ring_info = [ObjInfo(r['name'], r['prob'], r['worth']) for r in RING_INFO]
    game.ws_info = [ObjInfo(r['name'], r['prob'], r['worth']) for r in WS_INFO]
    game.weap_info = [ObjInfo(r['name'], r['prob'], r['worth']) for r in WEAPONS]
    game.arm_info = [ObjInfo(r['name'], r['prob'], r['worth']) for r in ARMORS]
    for tbl in (game.things, game.pot_info, game.scr_info, game.ring_info,
                game.ws_info, game.weap_info, game.arm_info):
        sumprobs(tbl)


def pick_color(game, col):
    """init.c:448 -- a random colour if hallucinating, else the given one."""
    return RAINBOW[rnd(len(RAINBOW))] if on(game.player, ISHALU) else col


def init_player(game):
    """init.c:24 -- starting kit: food, ring mail, a +1,+1 mace, a +1 bow, arrows."""
    game.player.t_stats = game.max_stats.copy()
    game.food_left = HUNGERTIME

    obj = Obj()
    obj.o_type = FOOD
    obj.o_count = 1
    add_pack(game, obj, True)

    obj = Obj()
    obj.o_type = ARMOR
    obj.o_which = RING_MAIL
    obj.o_arm = ARMORS[RING_MAIL]['ac'] - 1
    obj.o_flags |= ISKNOW
    obj.o_count = 1
    game.cur_armor = obj
    add_pack(game, obj, True)

    obj = Obj()
    init_weapon(game, obj, MACE)
    obj.o_hplus = 1
    obj.o_dplus = 1
    obj.o_flags |= ISKNOW
    add_pack(game, obj, True)
    game.cur_weapon = obj

    obj = Obj()
    init_weapon(game, obj, BOW)
    obj.o_hplus = 1
    obj.o_flags |= ISKNOW
    add_pack(game, obj, True)

    obj = Obj()
    init_weapon(game, obj, ARROW)
    obj.o_count = rnd(15) + 25
    obj.o_flags |= ISKNOW
    add_pack(game, obj, True)


def init_weapon(game, weap, which):
    """weapons.c:159"""
    weap.o_type = WEAPON
    weap.o_which = which
    iwp = WEAPONS[which]
    weap.o_damage = iwp['dmg']
    weap.o_hurldmg = iwp['hurl_dmg']
    weap.o_launch = iwp['launch'] if iwp['launch'] is not None else NO_WEAPON
    weap.o_flags = iwp['flags']
    weap.o_hplus = 0
    weap.o_dplus = 0
    if which == DAGGER:
        weap.o_count = rnd(4) + 2
        game.group += 1
        weap.o_group = game.group
    elif weap.o_flags & ISMANY:
        weap.o_count = rnd(8) + 8
        game.group += 1
        weap.o_group = game.group
    else:
        weap.o_count = 1
        weap.o_group = 0


def fix_stick(game, cur):
    """sticks.c:25"""
    if game.ws_type[cur.o_which] == "staff":
        cur.o_damage = "2x3"
    else:
        cur.o_damage = "1x1"
    cur.o_hurldmg = "1x1"
    if cur.o_which == WS_LIGHT:
        cur.o_charges = rnd(10) + 10
    else:
        cur.o_charges = rnd(5) + 3


# ---------------------------------------------------------------------------
# things.c
# ---------------------------------------------------------------------------

def pick_one(info):
    """things.c:314 -- pick an item out of a list of possible objects.

    info carries CUMULATIVE probabilities after sumprobs().
    """
    i = rnd(100)
    for idx in range(len(info)):
        if i < info[idx].oi_prob:
            return idx
    return 0                    # the C falls back to the first entry


def new_thing(game):
    """things.c:236 -- return a new random item."""
    cur = Obj()
    cur.o_hplus = 0
    cur.o_dplus = 0
    cur.o_damage = "0x0"
    cur.o_hurldmg = "0x0"
    cur.o_arm = 11
    cur.o_count = 1
    cur.o_group = 0
    cur.o_flags = 0

    # If we haven't had food for a while, let it be food.  things.c:252
    kind = 2 if game.no_food > 3 else pick_one(game.things)

    if kind == 0:
        cur.o_type = POTION
        cur.o_which = pick_one(game.pot_info)
    elif kind == 1:
        cur.o_type = SCROLL
        cur.o_which = pick_one(game.scr_info)
    elif kind == 2:
        cur.o_type = FOOD
        game.no_food = 0
        cur.o_which = 0 if rnd(10) != 0 else 1
    elif kind == 3:
        init_weapon(game, cur, pick_one(game.weap_info))
        r = rnd(100)
        if r < 10:
            cur.o_flags |= ISCURSED
            cur.o_hplus -= rnd(3) + 1
        elif r < 15:
            cur.o_hplus += rnd(3) + 1
    elif kind == 4:
        cur.o_type = ARMOR
        cur.o_which = pick_one(game.arm_info)
        cur.o_arm = ARMORS[cur.o_which]['ac']
        r = rnd(100)
        if r < 20:
            cur.o_flags |= ISCURSED
            cur.o_arm += rnd(3) + 1
        elif r < 28:
            cur.o_arm -= rnd(3) + 1
    elif kind == 5:
        cur.o_type = RING
        cur.o_which = pick_one(game.ring_info)
        w = cur.o_which
        if w in (R_ADDSTR, R_PROTECT, R_ADDHIT, R_ADDDAM):
            cur.o_arm = rnd(3)
            if cur.o_arm == 0:
                cur.o_arm = -1
                cur.o_flags |= ISCURSED
        elif w in (R_AGGR, R_TELEPORT):
            cur.o_flags |= ISCURSED
    elif kind == 6:
        cur.o_type = STICK
        cur.o_which = pick_one(game.ws_info)
        fix_stick(game, cur)
    return cur


def is_magic(obj):
    """weapons.c -- is this object magic (and so worth a nymph stealing)?"""
    t = obj.o_type
    if t == ARMOR:
        # potions.c:237 -- protected armor counts as magic even unenchanted
        return bool(obj.o_flags & ISPROT) or obj.o_arm != ARMORS[obj.o_which]["ac"]
    if t == WEAPON:
        return obj.o_hplus != 0 or obj.o_dplus != 0
    return t in (POTION, SCROLL, STICK, RING, AMULET)


def ring_num(game, obj):
    """rings.c:ring_num -- the "+N" shown on an identified ring."""
    if not (obj.o_flags & ISKNOW):
        return ""
    if obj.o_which in (R_PROTECT, R_ADDSTR, R_ADDDAM, R_ADDHIT):
        return " %s " % num(obj.o_arm, 0, RING)
    return ""


def charge_str(game, obj):
    """sticks.c:charge_str -- the charge count shown on an identified stick."""
    if obj.o_flags & ISKNOW:
        return " [%d charges] " % obj.o_charges
    return ""


def nameit(game, obj, type_name, which_name, op, prfunc):
    """things.c:479 -- name a potion, stick, or ring."""
    if op.oi_know or op.oi_guess:
        if obj.o_count == 1:
            head = "A %s " % type_name
        else:
            head = "%d %ss " % (obj.o_count, type_name)
        extra = prfunc(game, obj) if prfunc else ""
        if op.oi_know:
            return head + "of %s%s(%s)" % (op.oi_name, extra, which_name)
        return head + "called %s%s(%s)" % (op.oi_guess, extra, which_name)
    if obj.o_count == 1:
        return "A%s %s %s" % (vowelstr(which_name), which_name, type_name)
    return "%d %s %ss" % (obj.o_count, which_name, type_name)


def inv_name(game, obj, drop_case):
    """things.c:24 -- the name of something as it appears in an inventory."""
    if obj is None:
        return "nothing"
    which = obj.o_which
    t = obj.o_type
    pb = ""

    if t == POTION:
        pb = nameit(game, obj, "potion", game.p_colors[which],
                    game.pot_info[which], None)
    elif t == RING:
        pb = nameit(game, obj, "ring", game.r_stones[which],
                    game.ring_info[which], ring_num)
    elif t == STICK:
        pb = nameit(game, obj, game.ws_type[which], game.ws_made[which],
                    game.ws_info[which], charge_str)
    elif t == SCROLL:
        if obj.o_count == 1:
            pb = "A scroll "
        else:
            pb = "%d scrolls " % obj.o_count
        op = game.scr_info[which]
        if op.oi_know:
            pb += "of %s" % op.oi_name
        elif op.oi_guess:
            pb += "called %s" % op.oi_guess
        else:
            pb += "titled '%s'" % game.s_names[which]
    elif t == FOOD:
        if which == 1:
            if obj.o_count == 1:
                pb = "A%s %s" % (vowelstr(FRUIT), FRUIT)
            else:
                pb = "%d %ss" % (obj.o_count, FRUIT)
        else:
            if obj.o_count == 1:
                pb = "Some food"
            else:
                pb = "%d rations of food" % obj.o_count
    elif t == WEAPON:
        sp = WEAPONS[which]['name']
        if obj.o_count > 1:
            pb = "%d " % obj.o_count
        else:
            pb = "A%s " % vowelstr(sp)
        if obj.o_flags & ISKNOW:
            pb += "%s %s" % (num(obj.o_hplus, obj.o_dplus, WEAPON), sp)
        else:
            pb += "%s" % sp
        if obj.o_count > 1:
            pb += "s"
        if obj.o_label is not None:
            pb += " called %s" % obj.o_label
    elif t == ARMOR:
        sp = ARMORS[which]['name']
        if obj.o_flags & ISKNOW:
            pb = "%s %s [" % (num(ARMORS[which]['ac'] - obj.o_arm, 0, ARMOR), sp)
            if not game.terse:
                pb += "protection "
            pb += "%d]" % (10 - obj.o_arm)
        else:
            pb = "%s" % sp
        if obj.o_label is not None:
            pb += " called %s" % obj.o_label
    elif t == AMULET:
        pb = "The Amulet of Yendor"
    elif t == GOLD:
        pb = "%d Gold pieces" % obj.o_goldval
    else:
        pb = "Something bizarre %s" % obj.o_type

    # inv_describe is on by default in the C
    if obj is game.cur_armor:
        pb += " (being worn)"
    if obj is game.cur_weapon:
        pb += " (weapon in hand)"
    if obj is game.cur_ring[LEFT]:
        pb += " (on left hand)"
    elif obj is game.cur_ring[RIGHT]:
        pb += " (on right hand)"

    if drop_case and pb[:1].isupper():
        pb = pb[0].lower() + pb[1:]
    elif not drop_case and pb[:1].islower():
        pb = pb[0].upper() + pb[1:]
    return pb


def drop(game, obj):
    """things.c:137 -- put something down."""
    ch = game.chat(game.hero.y, game.hero.x)
    if ch != FLOOR and ch != PASSAGE:
        game.after = False
        msg(game, "there is something there already")
        return
    if obj is None:
        return
    if not dropcheck(game, obj):
        return
    is_mult = obj.o_type in (POTION, SCROLL, FOOD)
    obj = leave_pack(game, obj, True, not is_mult)
    game.lvl_obj.append(obj)
    game.set_chat(game.hero.y, game.hero.x, obj.o_type)
    game.set_flat(game.hero.y, game.hero.x,
                  game.flat(game.hero.y, game.hero.x) | F_DROPPED)
    obj.o_pos = game.hero.copy()
    if obj.o_type == AMULET:
        game.amulet = False
    msg(game, "dropped %s" % inv_name(game, obj, True))


def dropcheck(game, obj):
    """things.c:171 -- special checks for dropping or removing worn items."""
    if obj is None:
        return True
    if (obj is not game.cur_armor and obj is not game.cur_weapon
            and obj is not game.cur_ring[LEFT]
            and obj is not game.cur_ring[RIGHT]):
        return True
    if obj.o_flags & ISCURSED:
        msg(game, "you can't.  It appears to be cursed")
        return False
    if obj is game.cur_weapon:
        game.cur_weapon = None
    elif obj is game.cur_armor:
        waste_time(game)
        game.cur_armor = None
    else:
        game.cur_ring[LEFT if obj is game.cur_ring[LEFT] else RIGHT] = None
        if obj.o_which == R_ADDSTR:
            chg_str(game, -obj.o_arm)
        elif obj.o_which == R_SEEINVIS:
            unsee(game)
            extinguish(game, unsee)
    return True


# ---------------------------------------------------------------------------
# pack.c
# ---------------------------------------------------------------------------

def update_mdest(game, obj):
    """pack.c:18 -- a monster whose goal we just took gets mad at the hero."""
    for mp in game.mlist:
        if mp.t_dest is obj.o_pos:
            mp.t_dest = game.hero


def pack_char(game):
    """pack.c:227 -- return the next unused pack letter."""
    for i in range(26):
        if not game.pack_used[i]:
            game.pack_used[i] = True
            return chr(ord('a') + i)
    return chr(ord('a') + 25)


def pack_room(game, from_floor, obj):
    """pack.c:161 -- see if there's room in the pack."""
    game.inpack += 1
    if game.inpack > MAXPACK:
        if not game.terse:
            addmsg(game, "there's ")
        addmsg(game, "no room")
        if not game.terse:
            addmsg(game, " in your pack")
        endmsg(game)
        if from_floor:
            move_msg(game, obj)
        game.inpack = MAXPACK
        return False
    if from_floor:
        if obj in game.lvl_obj:
            game.lvl_obj.remove(obj)
        game.screen.mvaddch(game.hero.y, game.hero.x, floor_ch(game))
        game.set_chat(game.hero.y, game.hero.x,
                      PASSAGE if (game.proom.r_flags & ISGONE) else FLOOR)
    return True


def add_pack(game, obj, silent):
    """pack.c:36 -- pick up an object and add it to the pack.

    PORT NOTE: the C threads a hand-rolled doubly linked list and uses two
    gotos to keep same-type items grouped.  Same rules, expressed as a search
    over the list for a stackable match followed by an ordered insert.
    """
    from_floor = False
    if obj is None:
        obj = find_obj(game, game.hero.y, game.hero.x)
        if obj is None:
            return
        from_floor = True

    # Scare monster scrolls turn to dust when picked up a second time.
    if obj.o_type == SCROLL and obj.o_which == S_SCARE and (obj.o_flags & ISFOUND):
        if obj in game.lvl_obj:
            game.lvl_obj.remove(obj)
        game.screen.mvaddch(game.hero.y, game.hero.x, floor_ch(game))
        game.set_chat(game.hero.y, game.hero.x,
                      PASSAGE if (game.proom.r_flags & ISGONE) else FLOOR)
        update_mdest(game, obj)
        msg(game, "the scroll turns to dust as you pick it up")
        return

    stacked = None
    for op in game.pack:
        if op.o_type != obj.o_type or op.o_which != obj.o_which:
            continue
        if op.o_type in (POTION, SCROLL, FOOD):         # ISMULT
            stacked = op
            break
        if obj.o_group and op.o_group == obj.o_group:
            stacked = op
            break

    if stacked is not None:
        if stacked.o_type in (POTION, SCROLL, FOOD):
            if not pack_room(game, from_floor, obj):
                return
            stacked.o_count += 1
        else:
            stacked.o_count += obj.o_count
            game.inpack -= 1
            if not pack_room(game, from_floor, obj):
                return
        update_mdest(game, obj)
        obj = stacked
    else:
        if not pack_room(game, from_floor, obj):
            return
        obj.o_packch = pack_char(game)
        # keep the pack grouped by type, as the C's insertion does
        insert_at = len(game.pack)
        for i, op in enumerate(game.pack):
            if op.o_type == obj.o_type:
                insert_at = i + 1
        game.pack.insert(insert_at, obj)
        update_mdest(game, obj)

    obj.o_flags |= ISFOUND
    if obj.o_type == AMULET:
        game.amulet = True
    if not silent:
        if not game.terse:
            addmsg(game, "you now have ")
        msg(game, "%s (%c)" % (inv_name(game, obj, not game.terse), obj.o_packch))


def leave_pack(game, obj, newobj, all_of_them):
    """pack.c:191 -- take an item out of the pack."""
    game.inpack -= 1
    nobj = obj
    if obj.o_count > 1 and not all_of_them:
        game.last_pick = obj
        obj.o_count -= 1
        if obj.o_group:
            game.inpack += 1
        if newobj:
            nobj = Obj()
            for slot in Obj.__slots__:
                setattr(nobj, slot, getattr(obj, slot))
            nobj.o_pos = obj.o_pos.copy()
            nobj.o_count = 1
    else:
        game.last_pick = None
        idx = ord(obj.o_packch) - ord('a')
        if 0 <= idx < 26:
            game.pack_used[idx] = False
        if obj in game.pack:
            game.pack.remove(obj)
    return nobj


def inventory(game, lst, type_ch):
    """pack.c:247 -- the lines of the pack listing, filtered by type."""
    lines = []
    game.n_objs = 0
    for item in lst:
        if type_ch and type_ch != item.o_type:
            # pack.c:252 -- CALLABLE means the four namable classes, not
            # "anything that isn't food or the amulet"
            callable_ok = (type_ch == CALLABLE
                           and item.o_type in (SCROLL, POTION, RING, STICK))
            r_or_s_ok = (type_ch == R_OR_S and item.o_type in (RING, STICK))
            if not callable_ok and not r_or_s_ok:
                continue
        game.n_objs += 1
        lines.append("%c) %s" % (item.o_packch, inv_name(game, item, False)))
    if game.n_objs == 0:
        if game.terse:
            msg(game, "empty handed" if type_ch == 0 else "nothing appropriate")
        else:
            msg(game, "you are empty handed" if type_ch == 0
                else "you don't have anything appropriate")
        return []
    return lines


def pick_up(game, ch):
    """pack.c:297 -- add something to the character's pack."""
    if on(game.player, ISLEVIT):
        return
    obj = find_obj(game, game.hero.y, game.hero.x)
    if ch == GOLD:
        if obj is None:
            return
        money(game, obj.o_goldval)
        if obj in game.lvl_obj:
            game.lvl_obj.remove(obj)
        update_mdest(game, obj)
        if game.proom is not None:
            game.proom.r_goldval = 0
    else:
        add_pack(game, None, False)


def move_msg(game, obj):
    """pack.c:338 -- the message for moving onto an object."""
    if obj is None:
        return
    if not game.terse:
        addmsg(game, "you ")
    msg(game, "moved onto %s" % inv_name(game, obj, True))


def money(game, value):
    """pack.c:408 -- add or subtract gold."""
    game.purse += value
    game.screen.mvaddch(game.hero.y, game.hero.x, floor_ch(game))
    game.set_chat(game.hero.y, game.hero.x,
                  PASSAGE if (game.proom.r_flags & ISGONE) else FLOOR)
    if value > 0:
        if not game.terse:
            addmsg(game, "you found ")
        msg(game, "%d gold pieces" % value)


def floor_ch(game):
    """pack.c:429 -- the appropriate floor character for her room."""
    if game.proom is not None and (game.proom.r_flags & ISGONE):
        return PASSAGE
    return FLOOR if show_floor(game) else ' '


def floor_at(game):
    """pack.c:442 -- the character at the hero's position."""
    ch = game.chat(game.hero.y, game.hero.x)
    if ch == FLOOR:
        ch = floor_ch(game)
    return ch


def set_order(n):
    """things.c:392 -- a shuffled order for the discoveries list."""
    order = list(range(n))
    for i in range(n, 0, -1):
        r = rnd(i)
        order[i - 1], order[r] = order[r], order[i - 1]
    return order


def print_disc(game, type_ch):
    """things.c:352 -- what we've discovered of the given type."""
    if type_ch == SCROLL:
        info = game.scr_info
    elif type_ch == POTION:
        info = game.pot_info
    elif type_ch == RING:
        info = game.ring_info
    elif type_ch == STICK:
        info = game.ws_info
    else:
        return []

    lines = []
    obj = Obj()
    obj.o_count = 1
    obj.o_flags = 0
    for i in set_order(len(info)):
        if info[i].oi_know or info[i].oi_guess:
            obj.o_type = type_ch
            obj.o_which = i
            lines.append(inv_name(game, obj, False))
    if not lines:
        lines.append(nothing(game, type_ch))
    return lines


def nothing(game, type_ch):
    """things.c:451 -- the "nothing found" message."""
    base = "Nothing" if game.terse else "Haven't discovered anything"
    if type_ch == '*':
        return base
    tystr = {POTION: "potion", SCROLL: "scroll",
             RING: "ring", STICK: "stick"}.get(type_ch, "thing")
    return base + " about any %ss" % tystr


# ---------------------------------------------------------------------------
# wizard.c -- identification
# ---------------------------------------------------------------------------

TYPE_NAMES = {                  # wizard.c:100
    POTION: "potion",
    SCROLL: "scroll",
    FOOD: "food",
    R_OR_S: "ring, wand or staff",
    RING: "ring",
    STICK: "wand or staff",
    WEAPON: "weapon",
    ARMOR: "armor",
}


def type_name(type_ch):
    """wizard.c:100"""
    return TYPE_NAMES.get(type_ch, "thing")


def set_know(game, obj, info):
    """wizard.c:81 -- set things up when we really know what a thing is."""
    info[obj.o_which].oi_know = True
    obj.o_flags |= ISKNOW
    info[obj.o_which].oi_guess = None


def identify_obj(game, obj):
    """wizard.c:58 -- the business half of whatis(): learn what obj is."""
    if obj is None:
        return
    t = obj.o_type
    if t == SCROLL:
        set_know(game, obj, game.scr_info)
    elif t == POTION:
        set_know(game, obj, game.pot_info)
    elif t == STICK:
        set_know(game, obj, game.ws_info)
    elif t in (WEAPON, ARMOR):
        obj.o_flags |= ISKNOW
    elif t == RING:
        set_know(game, obj, game.ring_info)
    msg(game, inv_name(game, obj, False))


def call_it(game, obj, name):
    """misc.c:546 -- name an unidentified item class."""
    if obj is None:
        return
    t = obj.o_type
    info = {POTION: game.pot_info, SCROLL: game.scr_info,
            RING: game.ring_info, STICK: game.ws_info}.get(t)
    if info is None:
        msg(game, "you can't call that anything")
        return
    entry = info[obj.o_which]
    if entry.oi_know:
        msg(game, "that has already been identified")
        return
    entry.oi_guess = name
    msg(game, "called %s" % name)


# ---------------------------------------------------------------------------
# Magic items and equipment.
# Ported from potions.c, scrolls.c, rings.c, sticks.c, armor.c and weapons.c
# ---------------------------------------------------------------------------

# potions.c:26 -- flag, daemon, duration, hallucinating text, straight text.
# The daemons are looked up by name at call time because they are defined
# further down the assembled file than this table.
P_ACTIONS = (
    (ISHUH, 'unconfuse', HUHDURATION,
     "what a tripy feeling!",
     "wait, what's going on here. Huh? What? Who?"),
    (ISHALU, 'come_down', SEEDURATION,
     "Oh, wow!  Everything seems so cosmic!",
     "Oh, wow!  Everything seems so cosmic!"),
    (0, None, 0, "", ""),                               # P_POISON
    (0, None, 0, "", ""),                               # P_STRENGTH
    (CANSEE, 'unsee', SEEDURATION, None, None),         # P_SEEINVIS (see below)
    (0, None, 0, "", ""),                               # P_HEALING
    (0, None, 0, "", ""),                               # P_MFIND
    (0, None, 0, "", ""),                               # P_TFIND
    (0, None, 0, "", ""),                               # P_RAISE
    (0, None, 0, "", ""),                               # P_XHEAL
    (0, None, 0, "", ""),                               # P_HASTE
    (0, None, 0, "", ""),                               # P_RESTORE
    (ISBLIND, 'sight', SEEDURATION,
     "oh, bummer!  Everything is dark!  Help!",
     "a cloak of darkness falls around you"),
    (ISLEVIT, 'land', HEALTIME,
     "oh, wow!  You're floating in the air!",
     "you start to float in the air"),
)

# rings.c:150 -- how much food each ring uses up
RING_USES = (
    1,      # R_PROTECT
    1,      # R_ADDSTR
    1,      # R_SUSTSTR
    -3,     # R_SEARCH
    -5,     # R_SEEINVIS
    0,      # R_NOP
    0,      # R_AGGR
    -3,     # R_ADDHIT
    -3,     # R_ADDDAM
    2,      # R_REGEN
    -2,     # R_DIGEST
    0,      # R_TELEPORT
    1,      # R_STEALTH
    1,      # R_SUSTARM
)


def _daemon_by_name(name):
    return globals()[name] if name else None


# ---------------------------------------------------------------------------
# potions.c
# ---------------------------------------------------------------------------

def do_pot(game, type_, knowit):
    """potions.c:305 -- a potion with the standard fuse-and-flag setup."""
    flags, dname, ptime, high, straight = P_ACTIONS[type_]
    if type_ == P_SEEINVIS:
        high = straight = "this potion tastes like %s juice" % FRUIT
    func = _daemon_by_name(dname)
    if not game.pot_info[type_].oi_know:
        game.pot_info[type_].oi_know = knowit
    t = spread(ptime)
    if not on(game.player, flags):
        game.player.t_flags |= flags
        fuse(game, func, 0, t, AFTER)
        look(game, False)
    else:
        lengthen(game, func, t)
    msg(game, choose_str(game, high, straight))


def quaff(game, obj):
    """potions.c:60 -- quaff a potion from the pack."""
    if obj is None:
        return
    if obj.o_type != POTION:
        if not game.terse:
            msg(game, "yuk! Why would you want to drink that?")
        else:
            msg(game, "that's undrinkable")
        return
    if obj is game.cur_weapon:
        game.cur_weapon = None

    trip = on(game.player, ISHALU)
    leave_pack(game, obj, False, False)
    w = obj.o_which

    if w == P_CONFUSE:
        do_pot(game, P_CONFUSE, not trip)
    elif w == P_POISON:
        game.pot_info[P_POISON].oi_know = True
        if game.is_wearing(R_SUSTSTR):
            msg(game, "you feel momentarily sick")
        else:
            chg_str(game, -(rnd(3) + 1))
            msg(game, "you feel very sick now")
            come_down(game)
    elif w == P_HEALING:
        game.pot_info[P_HEALING].oi_know = True
        game.pstats.s_hpt += roll(game.pstats.s_lvl, 4)
        if game.pstats.s_hpt > game.pstats.s_maxhp:
            game.pstats.s_maxhp += 1
            game.pstats.s_hpt = game.pstats.s_maxhp
        sight(game)
        msg(game, "you begin to feel better")
    elif w == P_STRENGTH:
        game.pot_info[P_STRENGTH].oi_know = True
        chg_str(game, 1)
        msg(game, "you feel stronger, now.  What bulging muscles!")
    elif w == P_MFIND:
        game.player.t_flags |= SEEMONST
        fuse(game, turn_see, True, HUHDURATION, AFTER)
        if not turn_see(game, False):
            msg(game, "you have a %s feeling for a moment, then it passes"
                % choose_str(game, "normal", "strange"))
    elif w == P_TFIND:
        # Potion of magic detection.  Show the magic items.  potions.c:127
        show = False
        for tp in game.lvl_obj:
            if is_magic(tp):
                show = True
                game.detected_magic.append(tp.o_pos.copy())
        for mp in game.mlist:
            for tp in mp.t_pack:
                if is_magic(tp):
                    show = True
                    game.detected_magic.append(mp.t_pos.copy())
        if show:
            game.pot_info[P_TFIND].oi_know = True
            msg(game, "You sense the presence of magic on this level.")
        else:
            msg(game, "you have a %s feeling for a moment, then it passes"
                % choose_str(game, "normal", "strange"))
    elif w == P_LSD:
        if not trip:
            if on(game.player, SEEMONST):
                turn_see(game, False)
            start_daemon(game, visuals, 0, BEFORE)
            game.seenstairs = seen_stairs(game)
        do_pot(game, P_LSD, True)
    elif w == P_SEEINVIS:
        show = on(game.player, CANSEE)
        do_pot(game, P_SEEINVIS, False)
        if not show:
            invis_on(game)
        sight(game)
    elif w == P_RAISE:
        game.pot_info[P_RAISE].oi_know = True
        msg(game, "you suddenly feel much more skillful")
        raise_level(game)
    elif w == P_XHEAL:
        game.pot_info[P_XHEAL].oi_know = True
        game.pstats.s_hpt += roll(game.pstats.s_lvl, 8)
        if game.pstats.s_hpt > game.pstats.s_maxhp:
            if game.pstats.s_hpt > game.pstats.s_maxhp + game.pstats.s_lvl + 1:
                game.pstats.s_maxhp += 1
            game.pstats.s_maxhp += 1
            game.pstats.s_hpt = game.pstats.s_maxhp
        sight(game)
        come_down(game)
        msg(game, "you begin to feel much better")
    elif w == P_HASTE:
        game.pot_info[P_HASTE].oi_know = True
        game.after = False
        if add_haste(game, True):
            msg(game, "you feel yourself moving much faster")
    elif w == P_RESTORE:
        if game.is_ring(LEFT, R_ADDSTR):
            game.pstats.s_str = add_str(game.pstats.s_str,
                                        -game.cur_ring[LEFT].o_arm)
        if game.is_ring(RIGHT, R_ADDSTR):
            game.pstats.s_str = add_str(game.pstats.s_str,
                                        -game.cur_ring[RIGHT].o_arm)
        if game.pstats.s_str < game.max_stats.s_str:
            game.pstats.s_str = game.max_stats.s_str
        if game.is_ring(LEFT, R_ADDSTR):
            game.pstats.s_str = add_str(game.pstats.s_str,
                                        game.cur_ring[LEFT].o_arm)
        if game.is_ring(RIGHT, R_ADDSTR):
            game.pstats.s_str = add_str(game.pstats.s_str,
                                        game.cur_ring[RIGHT].o_arm)
        msg(game, "hey, this tastes great.  It make you feel warm all over")
    elif w == P_BLIND:
        do_pot(game, P_BLIND, True)
    elif w == P_LEVIT:
        do_pot(game, P_LEVIT, True)


def invis_on(game):
    """potions.c:246 -- turn on the ability to see invisible."""
    game.player.t_flags |= CANSEE
    for mp in game.mlist:
        if on(mp, ISINVIS) and see_monst(game, mp) and not on(game.player, ISHALU):
            game.screen.mvaddch(mp.t_pos.y, mp.t_pos.x, mp.t_disguise)


def turn_see(game, turn_off):
    """potions.c:263 -- put monster detection on or off."""
    add_new = 0
    scr = game.screen
    for mp in game.mlist:
        scr.move(mp.t_pos.y, mp.t_pos.x)
        can_see = see_monst(game, mp)
        if turn_off:
            if not can_see:
                scr.addch(mp.t_oldch)
        else:
            if not can_see:
                scr.standout()
            if not on(game.player, ISHALU):
                scr.addch(mp.t_type)
            else:
                scr.addch(chr(rnd(26) + ord('A')))
            if not can_see:
                scr.standend()
                add_new += 1
    if turn_off:
        game.player.t_flags &= ~SEEMONST
    else:
        game.player.t_flags |= SEEMONST
    return add_new


def seen_stairs(game):
    """potions.c:298 -- has the player seen the stairs?"""
    if game.screen.inch(game.stairs.y, game.stairs.x) == STAIRS:
        return True
    if game.hero == game.stairs:
        return True
    tp = game.moat(game.stairs.y, game.stairs.x)
    if tp is not None:
        if see_monst(game, tp) and on(tp, ISRUN):
            return True
        if on(game.player, SEEMONST) and tp.t_oldch == STAIRS:
            return True
    return False


# ---------------------------------------------------------------------------
# scrolls.c
# ---------------------------------------------------------------------------

def read_scroll(game, obj):
    """scrolls.c:22 -- read a scroll and do the appropriate thing."""
    if obj is None:
        return
    if obj.o_type != SCROLL:
        if not game.terse:
            msg(game, "there is nothing on it to read")
        else:
            msg(game, "nothing to read")
        return
    if obj is game.cur_weapon:
        game.cur_weapon = None
    leave_pack(game, obj, False, False)
    w = obj.o_which

    if w == S_CONFUSE:
        game.player.t_flags |= CANHUH
        msg(game, "your hands begin to glow %s" % pick_color(game, "red"))
    elif w == S_ARMOR:
        if game.cur_armor is not None:
            game.cur_armor.o_arm -= 1
            game.cur_armor.o_flags &= ~ISCURSED
            msg(game, "your armor glows %s for a moment"
                % pick_color(game, "silver"))
    elif w == S_HOLD:
        # Stop all monsters within two spaces.  scrolls.c:68
        ch = 0
        for x in range(game.hero.x - 2, game.hero.x + 3):
            if not (0 <= x < NUMCOLS):
                continue
            for y in range(game.hero.y - 2, game.hero.y + 3):
                if not (0 <= y < NUMLINES - 1):     # scrolls.c:73
                    continue
                mon = game.moat(y, x)
                if mon is not None and on(mon, ISRUN):
                    mon.t_flags &= ~ISRUN
                    mon.t_flags |= ISHELD
                    ch += 1
        if ch:
            addmsg(game, "the monster")
            if ch > 1:
                addmsg(game, "s around you")
            addmsg(game, " freeze")
            if ch == 1:
                addmsg(game, "s")
            endmsg(game)
            game.scr_info[S_HOLD].oi_know = True
        else:
            msg(game, "you feel a strange sense of loss")
    elif w == S_SLEEP:
        game.scr_info[S_SLEEP].oi_know = True
        game.no_command += rnd(spread(5)) + 4       # SLEEPTIME
        game.player.t_flags &= ~ISRUN
        msg(game, "you fall asleep")
    elif w == S_CREATE:
        # Create a monster next to the hero.  scrolls.c:104
        i = 0
        mp = Coord()
        for y in range(game.hero.y - 1, game.hero.y + 2):
            for x in range(game.hero.x - 1, game.hero.x + 2):
                if y == game.hero.y and x == game.hero.x:
                    continue
                if not game.in_bounds(y, x):
                    continue
                if game.moat(y, x) is None:
                    ch = game.winat(y, x)
                    if not step_ok(ch):
                        continue
                    if ch == SCROLL:
                        fo = find_obj(game, y, x)
                        if fo is not None and fo.o_which == S_SCARE:
                            continue
                    i += 1
                    if rnd(i) == 0:
                        mp.y = y
                        mp.x = x
        if i == 0:
            msg(game, "you hear a faint cry of anguish in the distance")
        else:
            new_monster(game, Thing(), randmonster(game, False), mp)
    elif w in (S_ID_POTION, S_ID_SCROLL, S_ID_WEAPON, S_ID_ARMOR, S_ID_R_OR_S):
        id_type = {S_ID_POTION: POTION, S_ID_SCROLL: SCROLL,
                   S_ID_WEAPON: WEAPON, S_ID_ARMOR: ARMOR,
                   S_ID_R_OR_S: R_OR_S}
        game.scr_info[w].oi_know = True
        msg(game, "this scroll is an %s scroll" % game.scr_info[w].oi_name)
        # scrolls.c:158 calls whatis(TRUE, type), which prompts for an item.
        # The loop can't prompt from here, so it records what to ask for and
        # the loop picks it up when read_scroll returns.
        game.pending_whatis = id_type[w]
    elif w == S_MAP:
        magic_map(game)
    elif w == S_FDET:
        ch = False
        for o in game.lvl_obj:
            if o.o_type == FOOD:
                ch = True
                game.detected_food.append(o.o_pos.copy())
        if ch:
            game.scr_info[S_FDET].oi_know = True
            msg(game, "Your nose tingles and you smell food.")
        else:
            msg(game, "your nose tingles")
    elif w == S_TELEP:
        cur_room = game.proom
        teleport(game)
        if cur_room is not game.proom:
            game.scr_info[S_TELEP].oi_know = True
    elif w == S_ENCH:
        if game.cur_weapon is None or game.cur_weapon.o_type != WEAPON:
            msg(game, "you feel a strange sense of loss")
        else:
            game.cur_weapon.o_flags &= ~ISCURSED
            if rnd(2) == 0:
                game.cur_weapon.o_hplus += 1
            else:
                game.cur_weapon.o_dplus += 1
            msg(game, "your %s glows %s for a moment"
                % (WEAPONS[game.cur_weapon.o_which]['name'],
                   pick_color(game, "blue")))
    elif w == S_SCARE:
        msg(game, "you hear maniacal laughter in the distance")
    elif w == S_REMOVE:
        uncurse(game.cur_armor)
        uncurse(game.cur_weapon)
        uncurse(game.cur_ring[LEFT])
        uncurse(game.cur_ring[RIGHT])
        msg(game, choose_str(game,
                             "you feel in touch with the Universal Onenes",
                             "you feel as if somebody is watching over you"))
    elif w == S_AGGR:
        aggravate(game)
        msg(game, "you hear a high pitched humming noise")
    elif w == S_PROTECT:
        if game.cur_armor is not None:
            game.cur_armor.o_flags |= ISPROT
            msg(game, "your armor is covered by a shimmering %s shield"
                % pick_color(game, "gold"))
        else:
            msg(game, "you feel a strange sense of loss")

    look(game, True)


def magic_map(game):
    """scrolls.c:170 -- the scroll of magic mapping."""
    game.scr_info[S_MAP].oi_know = True
    msg(game, "oh, now this scroll has a map on it")
    scr = game.screen
    for y in range(1, NUMLINES - 1):
        for x in range(NUMCOLS):
            pp = game.place(y, x)
            ch = pp.p_ch
            if ch in (DOOR, STAIRS):
                pass
            elif ch in (HWALL, VWALL):
                if not (pp.p_flags & F_REAL):
                    ch = pp.p_ch = DOOR
                    pp.p_flags |= F_REAL
            elif ch == ' ':
                if pp.p_flags & F_REAL:
                    if pp.p_flags & F_PASS:
                        if not (pp.p_flags & F_REAL):
                            pp.p_ch = PASSAGE
                        pp.p_flags |= (F_SEEN | F_REAL)
                        ch = PASSAGE
                    else:
                        ch = ' '
                else:
                    pp.p_flags |= F_REAL
                    ch = pp.p_ch = PASSAGE
                    pp.p_flags |= (F_SEEN | F_REAL)
            elif ch == PASSAGE:
                if not (pp.p_flags & F_REAL):
                    pp.p_ch = PASSAGE
                pp.p_flags |= (F_SEEN | F_REAL)
                ch = PASSAGE
            elif ch == FLOOR:
                if pp.p_flags & F_REAL:
                    ch = ' '
                else:
                    ch = TRAP
                    pp.p_ch = TRAP
                    pp.p_flags |= (F_SEEN | F_REAL)
            else:
                if pp.p_flags & F_PASS:
                    if not (pp.p_flags & F_REAL):
                        pp.p_ch = PASSAGE
                    pp.p_flags |= (F_SEEN | F_REAL)
                    ch = PASSAGE
                else:
                    ch = ' '
            if ch != ' ':
                mon = pp.p_monst
                if mon is not None:
                    mon.t_oldch = ch
                if mon is None or not on(game.player, SEEMONST):
                    scr.mvaddch(y, x, ch)


def uncurse(obj):
    """scrolls.c:359"""
    if obj is not None:
        obj.o_flags &= ~ISCURSED


# ---------------------------------------------------------------------------
# rings.c
# ---------------------------------------------------------------------------

def ring_on(game, obj, hand):
    """rings.c:20 -- put a ring on a hand."""
    if obj is None:
        return
    if obj.o_type != RING:
        if not game.terse:
            msg(game, "it would be difficult to wrap that around a finger")
        else:
            msg(game, "not a ring")
        return
    if is_current(game, obj):
        return

    if game.cur_ring[LEFT] is None and game.cur_ring[RIGHT] is None:
        ring = hand if hand is not None else LEFT
    elif game.cur_ring[LEFT] is None:
        ring = LEFT
    elif game.cur_ring[RIGHT] is None:
        ring = RIGHT
    else:
        if not game.terse:
            msg(game, "you already have a ring on each hand")
        else:
            msg(game, "wearing two")
        return
    game.cur_ring[ring] = obj

    if obj.o_which == R_ADDSTR:
        chg_str(game, obj.o_arm)
    elif obj.o_which == R_SEEINVIS:
        invis_on(game)
    elif obj.o_which == R_AGGR:
        aggravate(game)

    if not game.terse:
        addmsg(game, "you are now wearing ")
    msg(game, "%s (%c)" % (inv_name(game, obj, True), obj.o_packch))


def ring_off(game, hand):
    """rings.c:88 -- take off a ring."""
    if game.cur_ring[LEFT] is None and game.cur_ring[RIGHT] is None:
        msg(game, "no rings" if game.terse else "you aren't wearing any rings")
        return
    if game.cur_ring[LEFT] is None:
        ring = RIGHT
    elif game.cur_ring[RIGHT] is None:
        ring = LEFT
    else:
        ring = hand if hand is not None else LEFT
    obj = game.cur_ring[ring]
    if obj is None:
        msg(game, "not wearing such a ring")
        return
    if dropcheck(game, obj):
        msg(game, "was wearing %s(%c)"
            % (inv_name(game, obj, True), obj.o_packch))


def ring_eat(game, hand):
    """rings.c:150 -- how much food does this ring use up?"""
    ring = game.cur_ring[hand]
    if ring is None:
        return 0
    eat = RING_USES[ring.o_which]
    if eat < 0:
        eat = 1 if rnd(-eat) == 0 else 0
    if ring.o_which == R_DIGEST:
        eat = -eat
    return eat


# ---------------------------------------------------------------------------
# armor.c
# ---------------------------------------------------------------------------

def wear(game, obj):
    """armor.c:17"""
    if obj is None:
        return
    if game.cur_armor is not None:
        addmsg(game, "you are already wearing some")
        if not game.terse:
            addmsg(game, ".  You'll have to take it off first")
        endmsg(game)
        game.after = False
        return
    if obj.o_type != ARMOR:
        msg(game, "you can't wear that")
        return
    waste_time(game)
    obj.o_flags |= ISKNOW
    sp = inv_name(game, obj, True)
    game.cur_armor = obj
    if not game.terse:
        addmsg(game, "you are now ")
    msg(game, "wearing %s" % sp)


def take_off(game):
    """armor.c:51"""
    obj = game.cur_armor
    if obj is None:
        game.after = False
        msg(game, "not wearing armor" if game.terse
            else "you aren't wearing any armor")
        return
    if not dropcheck(game, game.cur_armor):
        return
    game.cur_armor = None
    addmsg(game, "was" if game.terse else "you used to be")
    msg(game, " wearing %c) %s" % (obj.o_packch, inv_name(game, obj, True)))


def waste_time(game):
    """armor.c:78 -- do nothing but let other things happen."""
    do_daemons(game, BEFORE)
    do_fuses(game, BEFORE)
    do_daemons(game, AFTER)
    do_fuses(game, AFTER)


def rust_armor(game, arm):
    """move.c:410 -- an aquator corrodes armor."""
    if (arm is None or arm.o_type != ARMOR or arm.o_which == LEATHER
            or arm.o_arm >= 9):
        return
    if (arm.o_flags & ISPROT) or game.is_wearing(R_SUSTARM):
        if not game.to_death:
            msg(game, "the rust vanishes instantly")
        return
    arm.o_arm += 1
    if not game.terse:
        msg(game, "your armor appears to be weaker now. Oh my!")
    else:
        msg(game, "your armor weakens")


# ---------------------------------------------------------------------------
# weapons.c
# ---------------------------------------------------------------------------

def missile(game, ydelta, xdelta, obj):
    """weapons.c:42 -- fire a missile in a given direction."""
    if obj is None:
        return
    if not dropcheck(game, obj) or is_current(game, obj):
        return
    obj = leave_pack(game, obj, True, False)
    do_motion(game, obj, ydelta, xdelta)
    mon = game.moat(obj.o_pos.y, obj.o_pos.x)
    if mon is None or not hit_monster(game, obj.o_pos.y, obj.o_pos.x, obj):
        fall(game, obj, True)


def do_motion(game, obj, ydelta, xdelta):
    """weapons.c:69 -- move an object across the room."""
    obj.o_pos = game.hero.copy()
    guard = 0
    while True:
        guard += 1
        if guard > NUMCOLS * NUMLINES:
            break                       # never in the C; cheap safety here
        obj.o_pos.y += ydelta
        obj.o_pos.x += xdelta
        if not game.in_bounds(obj.o_pos.y, obj.o_pos.x):
            obj.o_pos.y -= ydelta
            obj.o_pos.x -= xdelta
            break
        ch = game.winat(obj.o_pos.y, obj.o_pos.x)
        if step_ok(ch) and ch != DOOR:
            continue
        break


def fall(game, obj, pr):
    """weapons.c:113 -- drop an item someplace around here."""
    fpos = Coord()
    if fallpos(game, obj.o_pos, fpos):
        pp = game.place(fpos.y, fpos.x)
        pp.p_ch = obj.o_type
        obj.o_pos = fpos.copy()
        if cansee(game, fpos.y, fpos.x):
            if pp.p_monst is not None:
                pp.p_monst.t_oldch = obj.o_type
            else:
                game.screen.mvaddch(fpos.y, fpos.x, obj.o_type)
        game.lvl_obj.append(obj)
        return
    if pr:
        if game.has_hit:
            endmsg(game)
            game.has_hit = False
        if obj.o_type == WEAPON:
            name = game.weap_names[obj.o_which]
        else:
            name = inv_name(game, obj, True)
        msg(game, "the %s vanishes as it hits the ground" % name)


def hit_monster(game, y, x, obj):
    """weapons.c:196"""
    return fight(game, Coord(x, y), obj, True)


def wield(game, obj):
    """weapons.c:224 -- pull out a certain weapon."""
    oweapon = game.cur_weapon
    if not dropcheck(game, game.cur_weapon):
        game.cur_weapon = oweapon
        return
    game.cur_weapon = oweapon
    if obj is None:
        game.after = False
        return
    if obj.o_type == ARMOR:
        msg(game, "you can't wield armor")
        game.after = False
        return
    if is_current(game, obj):
        game.after = False
        return
    sp = inv_name(game, obj, True)
    game.cur_weapon = obj
    if not game.terse:
        addmsg(game, "you are now ")
    msg(game, "wielding %s (%c)" % (sp, obj.o_packch))


# ---------------------------------------------------------------------------
# sticks.c
# ---------------------------------------------------------------------------

def do_zap(game, obj):
    """sticks.c:47 -- perform a zap with a wand."""
    if obj is None:
        return
    if obj.o_type != STICK:
        game.after = False
        msg(game, "you can't zap with that!")
        return
    if obj.o_charges == 0:
        msg(game, "nothing happens")
        return
    w = obj.o_which
    delta = game.delta

    if w == WS_LIGHT:
        game.ws_info[WS_LIGHT].oi_know = True
        if game.proom is None or (game.proom.r_flags & ISGONE):
            msg(game, "the corridor glows and then fades")
        else:
            game.proom.r_flags &= ~ISDARK
            enter_room(game, game.hero)
            addmsg(game, "the room is lit")
            if not game.terse:
                addmsg(game, " by a shimmering %s light" % pick_color(game, "blue"))
            endmsg(game)
    elif w == WS_DRAIN:
        if game.pstats.s_hpt < 2:
            msg(game, "you are too weak to use it")
            return
        drain(game)
    elif w in (WS_INVIS, WS_POLYMORPH, WS_TELAWAY, WS_TELTO, WS_CANCEL):
        y, x = game.hero.y, game.hero.x
        while game.in_bounds(y, x) and step_ok(game.winat(y, x)):
            y += delta.y
            x += delta.x
        if not game.in_bounds(y, x):
            y -= delta.y
            x -= delta.x
        tp = game.moat(y, x)
        if tp is not None:
            monster = tp.t_type
            if monster == 'F':
                game.player.t_flags &= ~ISHELD
            if w == WS_INVIS:
                tp.t_flags |= ISINVIS
                if cansee(game, y, x):
                    game.screen.mvaddch(y, x, tp.t_oldch)
            elif w == WS_POLYMORPH:
                pp = tp.t_pack
                if tp in game.mlist:
                    game.mlist.remove(tp)
                if see_monst(game, tp):
                    game.screen.mvaddch(y, x, game.chat(y, x))
                oldch = tp.t_oldch
                game.set_moat(y, x, None)
                monster = chr(rnd(26) + ord('A'))
                new_monster(game, tp, monster, Coord(x, y))
                if see_monst(game, tp):
                    game.screen.mvaddch(y, x, monster)
                tp.t_oldch = oldch
                tp.t_pack = pp
                if see_monst(game, tp):
                    game.ws_info[WS_POLYMORPH].oi_know = True
            elif w == WS_CANCEL:
                tp.t_flags |= ISCANC
                tp.t_flags &= ~(ISINVIS | CANHUH)
                tp.t_disguise = tp.t_type
                if see_monst(game, tp):
                    game.screen.mvaddch(y, x, tp.t_disguise)
            else:                       # WS_TELAWAY / WS_TELTO
                new_pos = Coord()
                if w == WS_TELAWAY:
                    while True:
                        find_floor(game, None, new_pos, 0, True)
                        if new_pos != game.hero:
                            break
                else:
                    new_pos.y = game.hero.y + delta.y
                    new_pos.x = game.hero.x + delta.x
                tp.t_dest = game.hero
                tp.t_flags |= ISRUN
                relocate(game, tp, new_pos)
    elif w == WS_MISSILE:
        game.ws_info[WS_MISSILE].oi_know = True
        bolt = Obj()
        bolt.o_type = '*'
        bolt.o_hurldmg = "1x4"
        bolt.o_hplus = 100
        bolt.o_dplus = 1
        bolt.o_flags = ISMISL
        if game.cur_weapon is not None:
            bolt.o_launch = game.cur_weapon.o_which
        do_motion(game, bolt, delta.y, delta.x)
        tp = game.moat(bolt.o_pos.y, bolt.o_pos.x)
        if tp is not None and not save_throw(VS_MAGIC, tp):
            hit_monster(game, bolt.o_pos.y, bolt.o_pos.x, bolt)
        elif game.terse:
            msg(game, "missle vanishes")
        else:
            msg(game, "the missle vanishes with a puff of smoke")
    elif w in (WS_HASTE_M, WS_SLOW_M):
        y, x = game.hero.y, game.hero.x
        while game.in_bounds(y, x) and step_ok(game.winat(y, x)):
            y += delta.y
            x += delta.x
        if not game.in_bounds(y, x):
            y -= delta.y
            x -= delta.x
        tp = game.moat(y, x)
        if tp is not None:
            if w == WS_HASTE_M:
                if on(tp, ISSLOW):
                    tp.t_flags &= ~ISSLOW
                else:
                    tp.t_flags |= ISHASTE
            else:
                if on(tp, ISHASTE):
                    tp.t_flags &= ~ISHASTE
                else:
                    tp.t_flags |= ISSLOW
                tp.t_turn = True
            runto(game, Coord(x, y))
    elif w in (WS_ELECT, WS_FIRE, WS_COLD):
        if w == WS_ELECT:
            name = "bolt"
        elif w == WS_FIRE:
            name = "flame"
        else:
            name = "ice"
        fire_bolt(game, game.hero, delta, name)
        game.ws_info[w].oi_know = True
    elif w == WS_NOP:
        pass

    obj.o_charges -= 1


def drain(game):
    """sticks.c:229 -- drain hit points from the player into the monsters."""
    if game.chat(game.hero.y, game.hero.x) == DOOR:
        corp = game.passages[game.flat(game.hero.y, game.hero.x) & F_PNUM]
    else:
        corp = None
    inpass = game.proom is not None and (game.proom.r_flags & ISGONE)

    drainee = []
    for mp in game.mlist:
        if (mp.t_room is game.proom or (corp is not None and mp.t_room is corp)
                or (inpass and game.chat(mp.t_pos.y, mp.t_pos.x) == DOOR
                    and game.passages[game.flat(mp.t_pos.y, mp.t_pos.x)
                                      & F_PNUM] is game.proom)):
            drainee.append(mp)
    if not drainee:
        msg(game, "you have a tingling feeling")
        return
    game.pstats.s_hpt //= 2
    cnt = game.pstats.s_hpt // len(drainee)
    for mp in list(drainee):
        mp.t_stats.s_hpt -= cnt
        if mp.t_stats.s_hpt <= 0:
            killed(game, mp, see_monst(game, mp))
        else:
            runto(game, mp.t_pos)


def fire_bolt(game, start, direction, name):
    """sticks.c:276 -- fire a bolt in a given direction."""
    bolt = Obj()
    bolt.o_type = WEAPON
    bolt.o_which = FLAME
    bolt.o_hurldmg = "6x6"
    bolt.o_damage = "6x6"
    bolt.o_hplus = 100
    bolt.o_dplus = 0
    game.weap_names[FLAME] = name          # sticks.c:315

    s = direction.y + direction.x
    if s == 0:
        dirch = '/'
    elif s in (1, -1):
        dirch = HWALL if direction.y == 0 else VWALL
    else:
        dirch = '\\'

    pos = start.copy()
    hit_hero = (start is not game.hero)
    used = False
    changed = False
    spotpos = []
    i = 0
    while i < BOLT_LENGTH and not used:
        i += 1
        pos.y += direction.y
        pos.x += direction.x
        if not game.in_bounds(pos.y, pos.x):
            break
        spotpos.append(pos.copy())
        ch = game.winat(pos.y, pos.x)

        bounce = False
        if ch == DOOR and not (game.hero == pos):
            bounce = True
        elif ch in (VWALL, HWALL, ' '):
            bounce = True

        if bounce:
            if not changed:
                hit_hero = not hit_hero
            changed = False
            direction.y = -direction.y
            direction.x = -direction.x
            spotpos.pop()
            i -= 1
            msg(game, "the %s bounces" % name)
            continue

        tp = game.moat(pos.y, pos.x)
        if not hit_hero and tp is not None:
            hit_hero = True
            changed = not changed
            tp.t_oldch = game.chat(pos.y, pos.x)
            if not save_throw(VS_MAGIC, tp):
                bolt.o_pos = pos.copy()
                used = True
                if tp.t_type == 'D' and name == "flame":
                    addmsg(game, "the flame bounces")
                    if not game.terse:
                        addmsg(game, " off the dragon")
                    endmsg(game)
                else:
                    hit_monster(game, pos.y, pos.x, bolt)
            elif ch != 'M' or tp.t_disguise == 'M':
                if start is game.hero:
                    runto(game, pos)
                if game.terse:
                    msg(game, "%s misses" % name)
                else:
                    msg(game, "the %s whizzes past %s"
                        % (name, set_mname(game, tp)))
        elif hit_hero and pos == game.hero:
            hit_hero = False
            changed = not changed
            if not save(game, VS_MAGIC):
                game.pstats.s_hpt -= roll(6, 6)
                if game.pstats.s_hpt <= 0:
                    if start is game.hero:
                        death(game, 'b')
                    else:
                        m = game.moat(start.y, start.x)
                        death(game, m.t_type if m is not None else 'b')
                    return
                used = True
                if game.terse:
                    msg(game, "the %s hits" % name)
                else:
                    msg(game, "you are hit by the %s" % name)
            else:
                msg(game, "the %s whizzes by you" % name)
        game.screen.mvaddch(pos.y, pos.x, dirch)

    game.bolt_trail = spotpos
    for c in spotpos:
        game.screen.mvaddch(c.y, c.x, game.chat(c.y, c.x))


# ---------------------------------------------------------------------------
# Hero movement.  Ported from move.c
# ---------------------------------------------------------------------------

def _rncolor():
    """move.c: rainbow[rnd(cNCOLORS)]"""
    return RAINBOW[rnd(len(RAINBOW))]


def do_run(game, ch):
    """move.c:27 -- start the hero running."""
    game.running = True
    game.after = False
    game.runch = ch


def do_move(game, dy, dx):
    """move.c:41 -- check that a move is legal and handle the consequences.

    PORT NOTE: the C version is built out of three gotos -- `over` (retry the
    move after a corridor turn), `hit_bound` (ran into a wall) and `move_stuff`
    (commit the move).  `over` becomes the outer loop, `hit_bound` a boolean,
    and `move_stuff` a nested function.  Control flow is otherwise identical.
    """
    game.firstmove = False
    if game.no_move:
        game.no_move -= 1
        msg(game, "you are still stuck in the bear trap")
        return

    def move_stuff(nh, fl):
        game.screen.mvaddch(game.hero.y, game.hero.x, floor_at(game))
        if (fl & F_PASS) and game.chat(game.oldpos.y, game.oldpos.x) == DOOR:
            leave_room(game, nh)
        # the hero's Coord object must be mutated, never rebound: monsters
        # hold a live reference to it as their chase destination
        game.hero.set(nh)

    # move.c:70 -- the `over:` label sits INSIDE the else branch, so a retry
    # from the passgo corner-turn recomputes hero+delta without re-rolling the
    # confusion check.  Rolling it per iteration would draw an extra rnd(5)
    # per corner and could turn a corridor turn into a random stumble.
    confused = on(game.player, ISHUH) and rnd(5) != 0
    first = True

    while True:                                         # the `over` label
        if first and confused:
            nh = rndmove(game, game.player)
            if nh == game.hero:
                game.after = False
                game.running = False
                game.to_death = False
                return
        else:
            nh = Coord(game.hero.x + dx, game.hero.y + dy)
        first = False

        hit_bound = (nh.x < 0 or nh.x >= NUMCOLS
                     or nh.y <= 0 or nh.y >= NUMLINES - 1)
        fl = 0
        ch = ' '
        if not hit_bound:
            if not diag_ok(game, game.hero, nh):
                game.after = False
                game.running = False
                return
            if game.running and game.hero == nh:
                game.after = False
                game.running = False
            fl = game.flat(nh.y, nh.x)
            ch = game.winat(nh.y, nh.x)
            if not (fl & F_REAL) and ch == FLOOR:
                if not on(game.player, ISLEVIT):
                    game.set_chat(nh.y, nh.x, TRAP)
                    ch = TRAP
                    game.set_flat(nh.y, nh.x, game.flat(nh.y, nh.x) | F_REAL)
            elif on(game.player, ISHELD) and ch != 'F':
                msg(game, "you are being held")
                return

        if hit_bound or ch in (' ', VWALL, HWALL):
            # move.c:105 -- passgo follows a corridor around a corner
            if (game.passgo and game.running and game.proom is not None
                    and (game.proom.r_flags & ISGONE)
                    and not on(game.player, ISBLIND)):
                turned = False
                if game.runch in ('h', 'l'):
                    b1 = (game.hero.y != 1
                          and turn_ok(game, game.hero.y - 1, game.hero.x))
                    b2 = (game.hero.y != NUMLINES - 2
                          and turn_ok(game, game.hero.y + 1, game.hero.x))
                    if b1 != b2:
                        if b1:
                            game.runch = 'k'
                            dy = -1
                        else:
                            game.runch = 'j'
                            dy = 1
                        dx = 0
                        turnref(game)
                        turned = True
                elif game.runch in ('j', 'k'):
                    b1 = (game.hero.x != 0
                          and turn_ok(game, game.hero.y, game.hero.x - 1))
                    b2 = (game.hero.x != NUMCOLS - 1
                          and turn_ok(game, game.hero.y, game.hero.x + 1))
                    if b1 != b2:
                        if b1:
                            game.runch = 'h'
                            dx = -1
                        else:
                            game.runch = 'l'
                            dx = 1
                        dy = 0
                        turnref(game)
                        turned = True
                if turned:
                    continue                            # goto over
            game.running = False
            game.after = False
            return

        if ch == DOOR:
            game.running = False
            if game.flat(game.hero.y, game.hero.x) & F_PASS:
                enter_room(game, nh)
            move_stuff(nh, fl)
            return

        if ch == TRAP:
            tr = be_trapped(game, nh)
            if tr == T_DOOR or tr == T_TELEP:
                return
            move_stuff(nh, fl)
            return

        if ch == PASSAGE:
            # In a corridor you can't tell whether you're leaving a maze room,
            # so proom must always be recalculated.  move.c:170
            game.proom = roomin(game, game.hero)
            move_stuff(nh, fl)
            return

        if ch == FLOOR:
            if not (fl & F_REAL):
                be_trapped(game, game.hero)
            move_stuff(nh, fl)
            return

        if ch == STAIRS:
            game.seenstairs = True
        game.running = False
        if isupper_ch(ch) or game.moat(nh.y, nh.x) is not None:
            fight(game, nh, game.cur_weapon, False)
            return
        if ch != STAIRS:
            game.take = ch
        move_stuff(nh, fl)
        return


def turn_ok(game, y, x):
    """move.c:206 -- is it legal to turn onto the given space?"""
    pp = game.place(y, x)
    return (pp.p_ch == DOOR
            or (pp.p_flags & (F_REAL | F_PASS)) == (F_REAL | F_PASS))


def turnref(game):
    """move.c:220 -- mark a passage turning as seen."""
    pp = game.place(game.hero.y, game.hero.x)
    if not (pp.p_flags & F_SEEN):
        pp.p_flags |= F_SEEN


def door_open(game, rp):
    """move.c:243 -- illuminate a room, waking anything in it."""
    if rp is None or (rp.r_flags & ISGONE):
        return
    for y in range(rp.r_pos.y, rp.r_pos.y + rp.r_max.y):
        for x in range(rp.r_pos.x, rp.r_pos.x + rp.r_max.x):
            if not game.in_bounds(y, x):
                continue
            if isupper_ch(game.winat(y, x)):
                wake_monster(game, y, x)


def be_trapped(game, tc):
    """move.c:261 -- the guy stepped on a trap.  Make him pay."""
    if on(game.player, ISLEVIT):
        return T_RUST          # anything that isn't a door or a teleport
    game.running = False
    game.count = 0
    pp = game.place(tc.y, tc.x)
    pp.p_ch = TRAP
    tr = pp.p_flags & F_TMASK
    pp.p_flags |= F_SEEN

    if tr == T_DOOR:
        game.level += 1
        new_level(game)
        msg(game, "you fell into a trap!")
    elif tr == T_BEAR:
        game.no_move += spread(3)                       # BEARTIME
        msg(game, "you are caught in a bear trap")
    elif tr == T_MYST:
        # move.c:286 -- a switch, so only the CHOSEN case evaluates its
        # rnd(NCOLORS).  Building a tuple of all eleven strings first would
        # draw four extra random numbers every time and show the wrong colour.
        which = rnd(11)
        if which == 0:
            msg(game, "you are suddenly in a parallel dimension")
        elif which == 1:
            msg(game, "the light in here suddenly seems %s" % _rncolor())
        elif which == 2:
            msg(game, "you feel a sting in the side of your neck")
        elif which == 3:
            msg(game, "multi-colored lines swirl around you, then fade")
        elif which == 4:
            msg(game, "a %s light flashes in your eyes" % _rncolor())
        elif which == 5:
            msg(game, "a spike shoots past your ear!")
        elif which == 6:
            msg(game, "%s sparks dance across your armor" % _rncolor())
        elif which == 7:
            msg(game, "you suddenly feel very thirsty")
        elif which == 8:
            msg(game, "you feel time speed up suddenly")
        elif which == 9:
            msg(game, "time now seems to be going slower")
        elif which == 10:
            msg(game, "you pack turns %s!" % _rncolor())
    elif tr == T_SLEEP:
        game.no_command += spread(5)                    # SLEEPTIME
        game.player.t_flags &= ~ISRUN
        msg(game, "a strange white mist envelops you and you fall asleep")
    elif tr == T_ARROW:
        if swing(game.pstats.s_lvl - 1, game.pstats.s_arm, 1):
            game.pstats.s_hpt -= roll(1, 6)
            if game.pstats.s_hpt <= 0:
                msg(game, "an arrow killed you")
                death(game, 'a')
            else:
                msg(game, "oh no! An arrow shot you")
        else:
            arrow = Obj()
            init_weapon(game, arrow, ARROW)
            arrow.o_count = 1
            arrow.o_pos = game.hero.copy()
            fall(game, arrow, False)
            msg(game, "an arrow shoots past you")
    elif tr == T_TELEP:
        # the hero is leaving, so look() won't lay the TRAP down for us
        teleport(game)
        game.screen.mvaddch(tc.y, tc.x, TRAP)
    elif tr == T_DART:
        if not swing(game.pstats.s_lvl + 1, game.pstats.s_arm, 1):
            msg(game, "a small dart whizzes by your ear and vanishes")
        else:
            game.pstats.s_hpt -= roll(1, 4)
            if game.pstats.s_hpt <= 0:
                msg(game, "a poisoned dart killed you")
                death(game, 'd')
                return tr
            if not game.is_wearing(R_SUSTSTR) and not save(game, VS_POISON):
                chg_str(game, -1)
            msg(game, "a small dart just hit you in the shoulder")
    elif tr == T_RUST:
        msg(game, "a gush of water hits you on the head")
        rust_armor(game, game.cur_armor)
    return tr


def rndmove(game, who):
    """move.c:352 -- move in a random direction if confused."""
    # move.c:368 draws Y first, then X.  Coord(x, y) would reverse that,
    # because Python evaluates arguments left to right.
    _ry = who.t_pos.y + rnd(3) - 1
    _rx = who.t_pos.x + rnd(3) - 1
    ret = Coord(_rx, _ry)
    y, x = ret.y, ret.x
    if y == who.t_pos.y and x == who.t_pos.x:
        return ret
    bad = False
    if not game.in_bounds(y, x) or not diag_ok(game, who.t_pos, ret):
        bad = True
    else:
        ch = game.winat(y, x)
        if not step_ok(ch):
            bad = True
        elif ch == SCROLL:
            for obj in game.lvl_obj:
                if y == obj.o_pos.y and x == obj.o_pos.x:
                    if obj.o_which == S_SCARE:
                        bad = True
                    break
    if bad:
        return who.t_pos.copy()
    return ret


def teleport(game):
    """wizard.c:200 -- teleport the hero to a random spot on the level."""
    scr = game.screen
    c = Coord()
    scr.mvaddch(game.hero.y, game.hero.x, floor_at(game))
    find_floor(game, None, c, 0, True)
    if roomin(game, c) is not game.proom:
        leave_room(game, game.hero)
        game.hero.set(c)
        enter_room(game, game.hero)
    else:
        game.hero.set(c)
        look(game, True)
    scr.mvaddch(game.hero.y, game.hero.x, PLAYER)
    # turn off ISHELD in case teleportation happened while fighting a flytrap.
    # Without this the hero stays held with the flytrap now across the level,
    # unkillable, and every subsequent move prints "you are being held" --
    # an unrecoverable soft-lock.  wizard.c:222
    if on(game.player, ISHELD):
        game.player.t_flags &= ~ISHELD
        game.vf_hit = 0
        MONSTERS[ord('F') - ord('A')]['dmg'] = "000x0"
    game.no_move = 0
    game.count = 0
    game.running = False
    game.to_death = False
    game.oldpos.set(game.hero)
    game.oldrp = game.proom


def search(game):
    """command.c:477 -- player gropes about him to find hidden things.

    Each hidden thing has its own discovery odds, and hallucination and
    blindness both make searching harder via probinc.
    """
    ey = game.hero.y + 1
    ex = game.hero.x + 1
    probinc = (3 if on(game.player, ISHALU) else 0)
    probinc += (2 if on(game.player, ISBLIND) else 0)
    found = False

    for y in range(game.hero.y - 1, ey + 1):
        for x in range(game.hero.x - 1, ex + 1):
            if y == game.hero.y and x == game.hero.x:
                continue
            if not game.in_bounds(y, x):
                continue
            fp = game.flat(y, x)
            if fp & F_REAL:
                continue

            ch = game.chat(y, x)
            hit = False
            if ch in (VWALL, HWALL):
                if rnd(5 + probinc) != 0:
                    continue
                game.set_chat(y, x, DOOR)
                msg(game, "a secret door")
                hit = True
            elif ch == FLOOR:
                if rnd(2 + probinc) != 0:
                    continue
                game.set_chat(y, x, TRAP)
                if not game.terse:
                    addmsg(game, "you found ")
                if on(game.player, ISHALU):
                    # a RANDOM trap name while tripping, and no F_SEEN
                    msg(game, TRAP_NAMES[rnd(NTRAPS)])
                else:
                    msg(game, TRAP_NAMES[fp & F_TMASK])
                    game.set_flat(y, x, game.flat(y, x) | F_SEEN)
                hit = True
            elif ch == ' ':
                if rnd(3 + probinc) != 0:
                    continue
                # the C sets the character here; without it a found secret
                # passage stays ' ', step_ok(' ') is False, and it is
                # permanently invisible and unwalkable
                game.set_chat(y, x, PASSAGE)
                hit = True

            if hit:                                     # the C's `foundone:`
                found = True
                game.set_flat(y, x, game.flat(y, x) | F_REAL)
                game.count = 0
                game.running = False

    if found:
        look(game, False)


def d_level(game):
    """command.c -- go down a level."""
    if game.chat(game.hero.y, game.hero.x) != STAIRS:
        msg(game, "I see no way down")
        return False
    if on(game.player, ISLEVIT):
        msg(game, "You can't.  You're floating off the ground!")
        return False
    game.level += 1
    new_level(game)
    return True


def u_level(game):
    """command.c -- go up a level."""
    if game.chat(game.hero.y, game.hero.x) != STAIRS:
        msg(game, "I see no way up")
        return False
    if on(game.player, ISLEVIT):
        msg(game, "You can't.  You're floating off the ground!")
        return False
    if not game.amulet:
        msg(game, "your way is magically blocked")
        return False
    game.level -= 1
    if game.level == 0:
        total_winner(game)
        return True
    new_level(game)
    msg(game, "you feel a wrenching sensation in your gut")
    return True


# ---------------------------------------------------------------------------
# The daemon/fuse scheduler and the scheduled effects.
# Ported from daemon.c and daemons.c
#
# A "daemon" runs every turn until killed; a "fuse" counts down and fires once.
# BEFORE and AFTER tag which half of the turn a slot belongs to.  Both live in
# the same fixed-size table in the C, distinguished by d_time == DAEMON.
# ---------------------------------------------------------------------------

BEFORE = 1                      # spread(1) is exactly 1  -- see the note below
AFTER = 2                       # spread(2) is exactly 2

# PORT NOTE: rogue.h writes these as BEFORE=spread(1) and AFTER=spread(2), but
# spread(nm) = nm - nm/20 + rnd(nm/10) with C integer division, so for nm <= 19
# both divisions are 0 and rnd(0) is 0.  They are therefore exactly 1 and 2 --
# which they must be, since they are compared for equality as slot type tags.

WANDERTIME = None               # computed per call: spread(70)


def d_slot(game):
    """daemon.c:24 -- find an empty slot in the daemon/fuse list."""
    for dev in game.d_list:
        if dev.d_type == EMPTY:
            return dev
    return None


def find_slot(game, func):
    """daemon.c:43 -- find a particular slot in the table."""
    for dev in game.d_list:
        if dev.d_type != EMPTY and dev.d_func is func:
            return dev
    return None


def start_daemon(game, func, arg, type_):
    """daemon.c:60 -- start a daemon."""
    dev = d_slot(game)
    if dev is None:
        return
    dev.d_type = type_
    dev.d_func = func
    dev.d_arg = arg
    dev.d_time = DAEMON


def kill_daemon(game, func):
    """daemon.c:77 -- remove a daemon from the list."""
    dev = find_slot(game, func)
    if dev is None:
        return
    dev.d_type = EMPTY


def do_daemons(game, flag):
    """daemon.c:93 -- run every active daemon with the current flag."""
    for dev in game.d_list:
        if dev.d_type == flag and dev.d_time == DAEMON:
            dev.d_func(game, dev.d_arg)


def fuse(game, func, arg, time, type_):
    """daemon.c:112 -- start a fuse to go off in a number of turns."""
    wire = d_slot(game)
    if wire is None:
        return
    wire.d_type = type_
    wire.d_func = func
    wire.d_arg = arg
    wire.d_time = time


def lengthen(game, func, xtime):
    """daemon.c:128 -- increase the time until a fuse goes off."""
    wire = find_slot(game, func)
    if wire is None:
        return
    wire.d_time += xtime


def extinguish(game, func):
    """daemon.c:143 -- put out a fuse."""
    wire = find_slot(game, func)
    if wire is None:
        return
    wire.d_type = EMPTY


def do_fuses(game, flag):
    """daemon.c:158 -- decrement counters and fire the fuses that are due."""
    for wire in game.d_list:
        if flag == wire.d_type and wire.d_time > 0:
            wire.d_time -= 1
            if wire.d_time == 0:
                wire.d_type = EMPTY
                wire.d_func(game, wire.d_arg)


# ---------------------------------------------------------------------------
# daemons.c -- the scheduled effects themselves
# ---------------------------------------------------------------------------

def doctor(game, arg=0):
    """daemons.c:18 -- a healing daemon that restores hit points after rest.

    quiet is incremented FIRST, so every test below is on the post-increment
    value.  The ring of regeneration sits outside both branches and so fires
    every single turn regardless of level or quiet.
    """
    lv = game.pstats.s_lvl
    ohp = game.pstats.s_hpt
    game.quiet += 1
    if lv < 8:
        if game.quiet + (lv << 1) > 20:
            game.pstats.s_hpt += 1
    else:
        if game.quiet >= 3:
            game.pstats.s_hpt += rnd(lv - 7) + 1
    if game.is_ring(LEFT, R_REGEN):
        game.pstats.s_hpt += 1
    if game.is_ring(RIGHT, R_REGEN):
        game.pstats.s_hpt += 1
    if ohp != game.pstats.s_hpt:
        # note: the comparison above happens BEFORE the clamp, so a heal that
        # is clamped straight back down still resets quiet
        if game.pstats.s_hpt > game.pstats.s_maxhp:
            game.pstats.s_hpt = game.pstats.s_maxhp
        game.quiet = 0


def swander(game, arg=0):
    """daemons.c:47 -- time to start rolling for wandering monsters."""
    start_daemon(game, rollwand, 0, BEFORE)


def rollwand(game, arg=0):
    """daemons.c:58 -- roll to see if a wandering monster starts up."""
    game.between += 1
    if game.between >= 4:
        if roll(1, 6) == 4:
            wanderer(game)
            kill_daemon(game, rollwand)
            fuse(game, swander, 0, spread(70), BEFORE)      # WANDERTIME
        game.between = 0


def unconfuse(game, arg=0):
    """daemons.c:77 -- release the poor player from his confusion."""
    game.player.t_flags &= ~ISHUH
    msg(game, "you feel less %s now" % choose_str(game, "trippy", "confused"))


def unsee(game, arg=0):
    """daemons.c:88 -- turn off the ability to see invisible."""
    for th in game.mlist:
        if on(th, ISINVIS) and see_monst(game, th):
            game.screen.mvaddch(th.t_pos.y, th.t_pos.x, th.t_oldch)
    game.player.t_flags &= ~CANSEE


def sight(game, arg=0):
    """daemons.c:103 -- he gets his sight back."""
    if on(game.player, ISBLIND):
        extinguish(game, sight)
        game.player.t_flags &= ~ISBLIND
        if game.proom is not None and not (game.proom.r_flags & ISGONE):
            enter_room(game, game.hero)
        msg(game, choose_str(game,
                             "far out!  Everything is all cosmic again",
                             "the veil of darkness lifts"))


def nohaste(game, arg=0):
    """daemons.c:120 -- end the hasting."""
    game.player.t_flags &= ~ISHASTE
    msg(game, "you feel yourself slowing down")


def stomach(game, arg=0):
    """daemons.c:131 -- digest the hero's food."""
    orig_hungry = game.hungry_state

    if game.food_left <= 0:
        game.food_left -= 1
        if game.food_left + 1 < -STARVETIME:
            death(game, 's')
            return
        # the hero is fainting
        if game.no_command or rnd(5) != 0:
            return
        game.no_command += rnd(8) + 4
        game.hungry_state = F_FAINT
        if not game.terse:
            addmsg(game, choose_str(
                game,
                "the munchies overpower your motor capabilities.  ",
                "you feel too weak from lack of food.  "))
        msg(game, choose_str(game, "You freak out", "You faint"))
    else:
        oldfood = game.food_left
        game.food_left -= (ring_eat(game, LEFT) + ring_eat(game, RIGHT)
                           + 1 - (1 if game.amulet else 0))
        if game.food_left < MORETIME <= oldfood:
            game.hungry_state = F_WEAK
            msg(game, choose_str(
                game,
                "the munchies are interfering with your motor capabilites",
                "you are starting to feel weak"))
        elif game.food_left < 2 * MORETIME <= oldfood:
            game.hungry_state = F_HUNGRY
            if game.terse:
                msg(game, choose_str(game, "getting the munchies",
                                     "getting hungry"))
            else:
                msg(game, choose_str(game, "you are getting the munchies",
                                     "you are starting to get hungry"))

    if game.hungry_state != orig_hungry:
        game.player.t_flags &= ~ISRUN
        game.running = False
        game.to_death = False
        game.count = 0


def come_down(game, arg=0):
    """daemons.c:188 -- take the hero down off her acid trip."""
    if not on(game.player, ISHALU):
        return
    kill_daemon(game, visuals)
    game.player.t_flags &= ~ISHALU
    if on(game.player, ISBLIND):
        return

    scr = game.screen
    for tp in game.lvl_obj:
        if cansee(game, tp.o_pos.y, tp.o_pos.x):
            scr.mvaddch(tp.o_pos.y, tp.o_pos.x, tp.o_type)

    seemonst = on(game.player, SEEMONST)
    for tp in game.mlist:
        scr.move(tp.t_pos.y, tp.t_pos.x)
        if cansee(game, tp.t_pos.y, tp.t_pos.x):
            if not on(tp, ISINVIS) or on(game.player, CANSEE):
                scr.addch(tp.t_disguise)
            else:
                scr.addch(game.chat(tp.t_pos.y, tp.t_pos.x))
        elif seemonst:
            scr.standout()
            scr.addch(tp.t_type)
            scr.standend()
    msg(game, "Everything looks SO boring now.")


def visuals(game, arg=0):
    """daemons.c:236 -- change the characters for a hallucinating player."""
    if not game.after or (game.running and game.jump):
        return
    scr = game.screen
    for tp in game.lvl_obj:
        if cansee(game, tp.o_pos.y, tp.o_pos.x):
            scr.mvaddch(tp.o_pos.y, tp.o_pos.x, rnd_thing(game))

    if not game.seenstairs and cansee(game, game.stairs.y, game.stairs.x):
        scr.mvaddch(game.stairs.y, game.stairs.x, rnd_thing(game))

    seemonst = on(game.player, SEEMONST)
    for tp in game.mlist:
        scr.move(tp.t_pos.y, tp.t_pos.x)
        if see_monst(game, tp):
            if tp.t_type == 'X' and tp.t_disguise != 'X':
                scr.addch(rnd_thing(game))
            else:
                scr.addch(chr(rnd(26) + ord('A')))
        elif seemonst:
            scr.standout()
            scr.addch(chr(rnd(26) + ord('A')))
            scr.standend()


def land(game, arg=0):
    """daemons.c:283 -- land from a levitation potion."""
    game.player.t_flags &= ~ISLEVIT
    msg(game, choose_str(game, "bummer!  You've hit the ground",
                         "you float gently to the ground"))


def runners_daemon(game, arg=0):
    """main.c -- the daemon slot that moves every running monster."""
    runners(game)


# ---------------------------------------------------------------------------
# Sprites.
#
# The deliverable is one file with no external assets, so the artwork cannot
# be loaded -- it has to BE code.  Each sprite is an 8x12 grid of characters
# indexing a fixed palette, which is how 8-bit hardware actually stored tiles:
# a small fixed palette, a low-resolution cell, and colour swaps to get more
# creatures out of the same silhouette.
#
# 8 wide x 12 tall is the classic text-cell ratio (VGA was 8x16, CGA 8x8), and
# it matches the 80x24 grid Rogue is built around.  Sprites are scaled up with
# nearest-neighbour so the pixels stay hard-edged instead of blurring.
# ---------------------------------------------------------------------------

SPRITE_W = 8
SPRITE_H = 12

# A fixed 16-ish colour palette, in the spirit of the EGA/NES era.
# '.' is transparent.
PALETTE = {
    '.': None,
    '0': (18, 16, 22),          # black / pupils
    '1': (34, 30, 40),          # outline
    '2': (255, 255, 255),       # white
    '3': (176, 180, 192),       # light grey / steel
    '4': (96, 100, 114),        # mid grey
    '5': (214, 66, 66),         # red
    '6': (128, 32, 32),         # dark red
    '7': (240, 190, 140),       # skin
    '8': (158, 102, 54),        # brown
    '9': (92, 62, 36),          # dark brown
    'a': (242, 200, 72),        # gold
    'b': (252, 248, 150),       # pale yellow
    'c': (104, 200, 104),       # green
    'd': (40, 112, 64),         # dark green
    'e': (120, 180, 245),       # pale blue
    'f': (56, 86, 190),         # blue
    'g': (186, 112, 222),       # purple
    'h': (244, 134, 200),       # pink
    'i': (96, 224, 214),        # cyan
    'j': (250, 146, 62),        # orange
    'k': (24, 26, 34),          # floor base
    'l': (40, 44, 56),          # floor speckle
    'm': (88, 76, 66),          # brick
    'n': (56, 48, 42),          # mortar
    'o': (120, 104, 92),        # brick highlight
    'p': (46, 40, 32),          # corridor base
    'q': (66, 56, 44),          # corridor grit
}

# ---------------------------------------------------------------------------
# Terrain and items
# ---------------------------------------------------------------------------

SPRITES = {}

SPRITES[FLOOR] = """
kkkkkkkk
kkkkkkkk
kklkkkkk
kkkkkkkk
kkkkkkkl
kkkkkkkk
kkkkkkkk
klkkkkkk
kkkkkkkk
kkkkkkkk
kkkkklkk
kkkkkkkk
"""

SPRITES[PASSAGE] = """
pppppppp
ppqppppp
pppppppp
ppppppqp
pppppppp
pqpppppp
pppppppp
ppppqppp
pppppppp
pppppppp
pppqpppp
pppppppp
"""

SPRITES[HWALL] = """
oooooooo
mmmnmmmm
mmmnmmmm
nnnnnnnn
mmmmmmmn
mmmmmmmn
nnnnnnnn
mmmnmmmm
mmmnmmmm
nnnnnnnn
mmmmmmmn
mmmmmmmn
"""

SPRITES[VWALL] = """
mmmnmmmm
mmmnmmmm
nnnnnnnn
mmmmmmmn
mmmmmmmn
nnnnnnnn
mmmnmmmm
mmmnmmmm
nnnnnnnn
mmmmmmmn
mmmmmmmn
nnnnnnnn
"""

SPRITES[DOOR] = """
nnnnnnnn
n888888n
n898898n
n888888n
n898898n
n888888n
n8888a8n
n888888n
n898898n
n888888n
n898898n
nnnnnnnn
"""

SPRITES[STAIRS] = """
kkkkkkkk
kkkkkkkk
kkkkk333
kkkkk311
kkk33333
kkk31111
k3333333
k3111111
33333333
31111111
kkkkkkkk
kkkkkkkk
"""

SPRITES[TRAP] = """
kkkkkkkk
kkkkkkkk
k333333k
3k3kk3k3
3kkkkkk3
36666663
36666663
3kkkkkk3
3k3kk3k3
k333333k
kkkkkkkk
kkkkkkkk
"""

SPRITES[GOLD] = """
kkkkkkkk
kkkkkkkk
kkkkkkkk
kkkabkkk
kkaabakk
kkaaaakk
kabkabkk
aabaabak
aaaaaaak
kaaaaaak
kkkkkkkk
kkkkkkkk
"""

SPRITES[POTION] = """
kkkkkkkk
kkk33kkk
kkk33kkk
kkk11kkk
kk3113kk
kk3113kk
k311113k
k3hhhh3k
k3hhhh3k
k3hhhh3k
kk3333kk
kkkkkkkk
"""

SPRITES[SCROLL] = """
kkkkkkkk
kkkkkkkk
k111111k
13bbbb31
13b11b31
13bbbb31
13b11b31
13bbbb31
13b11b31
13bbbb31
k111111k
kkkkkkkk
"""

SPRITES[FOOD] = """
kkkkkkkk
kkkkkkkk
kkkkk33k
kkkk883k
kkk88853
kk888853
k8885553
k8855553
k3555533
kk33333k
kkkkkkkk
kkkkkkkk
"""

SPRITES[WEAPON] = """
kkk33kkk
kkk33kkk
kkk33kkk
kkk33kkk
kkk33kkk
kkk33kkk
ka3333ak
kkk88kkk
kkk88kkk
kkk88kkk
kkk99kkk
kkkkkkkk
"""

SPRITES[ARMOR] = """
kkkkkkkk
k111111k
1f4444f1
1f4444f1
1f4444f1
1f4444f1
1f4444f1
k1f44f1k
kk1ff1kk
kkk11kkk
kkkkkkkk
kkkkkkkk
"""

SPRITES[RING] = """
kkkkkkkk
kkkkkkkk
kkkikkkk
kkaaakkk
kkakakkk
kaakaakk
kakkkakk
kakkkakk
kaakaakk
kkaaaakk
kkkkkkkk
kkkkkkkk
"""

SPRITES[STICK] = """
kkkkkkkk
kkkkkikk
kkkkiaik
kkkkkikk
kkkk9kkk
kkk9kkkk
kkk9kkkk
kk9kkkkk
kk9kkkkk
k9kkkkkk
kkkkkkkk
kkkkkkkk
"""

SPRITES[AMULET] = """
kkkkkkkk
kakkkkak
kkakkakk
kkkaakkk
kkaaaakk
kagggakk
kaggggak
kagggakk
kkaaaakk
kkkaakkk
kkkkkkkk
kkkkkkkk
"""

SPRITES[MAGIC] = """
kkkkkkkk
kkkbkkkk
kkkbkkkk
kkbbbkkk
bbbbbbbk
kkbbbkkk
kkkbkkkk
kkkbkkkk
kkkkkkkk
kkkkkkkk
kkkkkkkk
kkkkkkkk
"""

SPRITES[PLAYER] = """
kkkkkkkk
kk3333kk
k333333k
k377773k
k370770k
k377773k
kk7777kk
kffffffk
7ffffff7
kffffffk
kk9kk9kk
kk9kk9kk
"""

# ---------------------------------------------------------------------------
# Monsters, A-Z, in the order Rogue lists them
# ---------------------------------------------------------------------------

SPRITES['A'] = """
kkkkkkkk
kkkkkkkk
kiiiiikk
iiiiiiik
i0ii0iik
iiiiiiik
kiiiiiik
kkiiiikk
kiikkiik
kikkkkik
kkkkkkkk
kkkkkkkk
"""

SPRITES['B'] = """
kkkkkkkk
9kkkkkk9
99kkkk99
999kk999
99999999
k995599k
kk9559kk
kkk99kkk
kkkkkkkk
kkkkkkkk
kkkkkkkk
kkkkkkkk
"""

SPRITES['C'] = """
kkk77kkk
kk7777kk
kk7007kk
kkk77kkk
ka7777ak
ka8888ak
k888888k
88888888
88888888
k8kk8k8k
k8kk8k8k
k9kk9k9k
"""

SPRITES['D'] = """
kkkkkkkk
kddkkkkk
kdddkkkk
dd5ddkkk
ddddddkk
kddddddk
kkdddddd
kkddddkd
kdddddkd
kddkddkk
kdkkdkkk
kkkkkkkk
"""

SPRITES['E'] = """
kkkkkkkk
kkkk88kk
kkk8008k
kkkj888k
kkkk88kk
kkkk8kkk
kk8888kk
k888888k
k888888k
kk8888kk
kkk8k8kk
kkj8kj8k
"""

SPRITES['F'] = """
kkkkkkkk
kckkkckk
kcckkcck
kc2c2cck
kcc2ccck
kkccccck
kkkdddkk
kkkdddkk
kkkdddkk
kkdddddk
kddddddk
kkkkkkkk
"""

SPRITES['G'] = """
kkkkkkkk
kkkaakkk
kka00akk
kkjaaakk
kaaaaaak
aa8888aa
ka8888ak
k888888k
k88kk88k
k8kkkk8k
k9kkkk9k
kkkkkkkk
"""

SPRITES['H'] = """
kkkkkkkk
kkcccckk
kckccckc
kcc00cck
kkcccckk
kk6666kk
k666666k
c666666c
k666666k
kk6kk6kk
kk9kk9kk
kkkkkkkk
"""

SPRITES['I'] = """
kkkkkkkk
kk2222kk
k222222k
k2i22i2k
k222222k
ki2222ik
k222222k
ki2222ik
k222222k
kk2222kk
kkikkikk
kkkkkkkk
"""

SPRITES['J'] = """
kkkkkkkk
kgkkkkgk
kggkkggk
kgg55ggk
kggggggk
gg2gg2gg
kggggggk
kkgggggk
kggkkggk
kgkkkkgk
k9kkkk9k
kkkkkkkk
"""

SPRITES['K'] = """
kkkkkkkk
kkkjjkkk
kkj00jkk
kkajjakk
8kkjjkk8
88kjjk88
8j8jj8j8
k8jjjj8k
kkjjjjkk
kkkjjkkk
kkakakkk
kkkkkkkk
"""

SPRITES['L'] = """
kkkkkkkk
kkddddkk
kddddddk
kk7777kk
kk7007kk
kkk77kkk
kkddddkk
kddddddk
kaddddak
kkddddkk
kk9kk9kk
kkkkkkkk
"""

SPRITES['M'] = """
kkkkkkkk
ckckkckc
kcckkcck
kkccccck
kk7777kk
kk5775kk
kkk77kkk
kkcccckk
kcccccck
kkccccck
kkkcckkk
kkkkkkkk
"""

SPRITES['N'] = """
kkkkkkkk
kkahhakk
kahhhhak
kk7777kk
kk7007kk
kkk77kkk
kkhhhhkk
khhhhhhk
khhhhhhk
kkhhhhkk
kk7kk7kk
kkkkkkkk
"""

SPRITES['O'] = """
kkkkkkkk
kkddddkk
kddddddk
kd5dd5dk
kd2dd2dk
kkddddkk
kddddddk
8dddddd8
kddddddk
kkdkkdkk
kk9kk9kk
kkkkkkkk
"""

SPRITES['P'] = """
kkkkkkkk
kkeeeekk
keeeeeek
ke0ee0ek
keeeeeek
keeeeeek
keeeeeek
keeeeeek
keekeeek
kkekkekk
kkkkkkkk
kkkkkkkk
"""

SPRITES['Q'] = """
kkkkkkkk
kkkkkkkk
kkkkkk8k
kkkkk808
kkkkk888
kk888888
k2828288
82828288
k8888888
k8kk8k8k
k8kk8k8k
k9kk9k9k
"""

SPRITES['R'] = """
kkkkkkkk
kk8kkkkk
k808kkkk
k888kkkk
kk8888kk
kkkk888k
kk88888k
k888kk8k
k88kkk8k
k888888k
kkbbbkkk
kkkkkkkk
"""

SPRITES['S'] = """
kkkkkkkk
kkkkkkkk
kkccccck
kcckkkck
kckkkkkk
kcckkkkk
kkccccck
kkkkkkcc
kkkkkkck
kccccccc
cc0kkkkk
kkkkkkkk
"""

SPRITES['T'] = """
kkkkkkkk
kkddddkk
kddddddk
kd5dd5dk
kdd22ddk
kkddddkk
dddddddd
dddddddd
kddddddk
kddkkddk
k9kkkk9k
kkkkkkkk
"""

SPRITES['U'] = """
kkkkkk2k
kkkkk2kk
kkkk2kkk
kkk444kk
kk45044k
kk4444kk
k444444k
44444444
44444444
k4kk4k4k
k4kk4k4k
k1kk1k1k
"""

SPRITES['V'] = """
kkkkkkkk
kk1111kk
k111111k
k177771k
k175571k
kk7227kk
k611116k
61111116
k611116k
kk1111kk
kk1kk1kk
kkkkkkkk
"""

SPRITES['W'] = """
kkkkkkkk
kkk44kkk
kk4444kk
k444444k
k454454k
k444444k
k444444k
kk4444kk
k4k44k4k
kkk44kkk
kkkkkkkk
kkkkkkkk
"""

SPRITES['X'] = """
kkkkkkkk
kkkggkkk
kkggggkk
kggggggk
gg2gg2gg
kggggggk
kggggggk
kkggggkk
kgkggkgk
kkkggkkk
kkkkkkkk
kkkkkkkk
"""

SPRITES['Y'] = """
kkkkkkkk
kk2222kk
k222222k
k2e22e2k
k222222k
kk2222kk
k222222k
22222222
k222222k
k22kk22k
k2kkkk2k
kkkkkkkk
"""

SPRITES['Z'] = """
kkkkkkkk
kkddddkk
kddddddk
kd0dd0dk
kddddddk
kkd11dkk
kkddddkk
kddddddk
dddddddd
kddkkddk
kdkkkkdk
kkkkkkkk
"""


def _rows(art):
    return [r for r in art.strip("\n").split("\n")]


def validate_sprites():
    """Catch art typos at import time rather than as a blank tile in play."""
    bad = []
    for key, art in SPRITES.items():
        rows = _rows(art)
        if len(rows) != SPRITE_H:
            bad.append("%r has %d rows, want %d" % (key, len(rows), SPRITE_H))
            continue
        for n, row in enumerate(rows):
            if len(row) != SPRITE_W:
                bad.append("%r row %d is %d wide, want %d"
                           % (key, n, len(row), SPRITE_W))
            for c in row:
                if c not in PALETTE:
                    bad.append("%r row %d uses unknown colour %r" % (key, n, c))
    if bad:
        raise ValueError("sprite art errors:\n  " + "\n  ".join(bad))
    return True


def render_sprite(art, w, h, dim=False):
    """Rasterise one sprite to a Surface of exactly w x h pixels."""
    rows = _rows(art)
    surf = pygame.Surface((SPRITE_W, SPRITE_H), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            rgb = PALETTE.get(c)
            if rgb is None:
                continue
            if dim:
                rgb = (int(rgb[0] * 0.42), int(rgb[1] * 0.42), int(rgb[2] * 0.42))
            surf.set_at((x, y), rgb)
    # plain scale, not smoothscale: nearest-neighbour keeps the pixels crisp,
    # which is the entire point of the look
    return pygame.transform.scale(surf, (max(1, w), max(1, h)))


def build_sprite_sheet(w, h):
    """Rasterise every sprite at this cell size, lit and dimmed."""
    lit = {}
    dim = {}
    for key, art in SPRITES.items():
        lit[key] = render_sprite(art, w, h, dim=False)
        dim[key] = render_sprite(art, w, h, dim=True)
    return lit, dim


# ---------------------------------------------------------------------------
# The graphical interface.  This is the one part that is NOT a port -- it
# replaces curses entirely.  It is a pure function of the Screen buffer, the
# message queue and the player's stats, so it holds no game state of its own.
# ---------------------------------------------------------------------------

# Row 0 is the message line, rows 1..NUMLINES-2 are the map, and row
# NUMLINES-1 is the status line -- the same layout the curses version uses.
MAP_TOP = 1
MAP_BOTTOM = NUMLINES - 2

BG = (13, 14, 18)
BG_STATUS = (20, 22, 28)
FG_DEFAULT = (198, 202, 210)
FG_MSG = (236, 232, 208)
FG_MORE = (255, 214, 110)
FG_STATUS = (176, 184, 198)
FG_LOWHP = (226, 94, 94)
HILITE = (44, 52, 68)

# Colours by map character.  Monsters (A-Z) are coloured by tier further down.
TILE_COLORS = {
    PLAYER:  (255, 255, 255),
    VWALL:   (108, 116, 134),
    HWALL:   (108, 116, 134),
    FLOOR:   (88, 94, 110),
    PASSAGE: (122, 108, 84),
    DOOR:    (186, 138, 74),
    STAIRS:  (120, 220, 170),
    TRAP:    (222, 96, 108),
    GOLD:    (238, 198, 66),
    POTION:  (232, 118, 196),
    SCROLL:  (226, 226, 216),
    FOOD:    (204, 150, 92),
    WEAPON:  (150, 200, 236),
    ARMOR:   (140, 168, 220),
    RING:    (120, 226, 220),
    STICK:   (196, 160, 236),
    AMULET:  (255, 216, 90),
    MAGIC:   (255, 170, 240),
    '*':     (238, 198, 66),
    '\\':    (255, 236, 170),
}

# Monsters coloured roughly by how dangerous they are, using the C's own
# ordering in LVL_MONS: early letters are weak, later ones are lethal.
MONSTER_TIERS = (
    ((120, 200, 128), "KEBSH"),          # green   -- fodder
    ((214, 208, 120), "IROZLC"),         # yellow  -- routine
    ((226, 158, 88), "QANYFT"),          # orange  -- dangerous
    ((228, 104, 104), "WPXUM"),          # red     -- deadly
    ((236, 120, 236), "VGJD"),           # magenta -- nightmare
)


def _monster_color(ch):
    for color, letters in MONSTER_TIERS:
        if ch in letters:
            return color
    return (210, 210, 210)


def _dim(color, factor=0.42):
    return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))


class Renderer(object):
    """Draws the Screen buffer as a tile grid."""

    def __init__(self, game, cell_w=16, headless=False, sprites=True):
        self.game = game
        self.headless = headless
        self.glyph_cache = {}
        self.more_pending = False

        # Sprite mode uses a 2:3 cell so the 8x12 art scales without distortion;
        # text mode keeps the taller cell a monospace glyph wants.
        self.sprite_mode = sprites
        self.sprites = {}
        self.sprites_dim = {}

        self.cell_w = cell_w
        self.cell_h = self._cell_height(cell_w)
        w = self.cell_w * NUMCOLS
        h = self.cell_h * NUMLINES
        flags = pygame.RESIZABLE
        self.screen_surf = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption("Rogue -- Exploring the Dungeons of Doom")
        self.font = None
        self.small = None
        self._load_fonts()
        self.overlay = None             # list of lines, or None
        self.overlay_title = ""
        self._build_sprites()

    def _cell_height(self, cell_w):
        return int(cell_w * 1.5) if self.sprite_mode else int(cell_w * 1.9)

    def _build_sprites(self):
        if not self.sprite_mode:
            self.sprites = {}
            self.sprites_dim = {}
            return
        self.sprites, self.sprites_dim = build_sprite_sheet(self.cell_w,
                                                            self.cell_h)

    def set_sprite_mode(self, on):
        """Switch between pixel art and the original glyph grid."""
        if on == self.sprite_mode:
            return
        self.sprite_mode = on
        self.cell_h = self._cell_height(self.cell_w)
        self._load_fonts()
        self._build_sprites()

    # -- fonts -------------------------------------------------------------

    def _load_fonts(self):
        """Find a monospace face.  No external font files are shipped, so this
        walks the system list and falls back to pygame's built-in font."""
        size = int(self.cell_h * 0.86)
        for name in ("consolas", "dejavusansmono", "couriernew", "liberationmono",
                     "monospace"):
            try:
                f = pygame.font.SysFont(name, size)
                if f is not None:
                    self.font = f
                    break
            except Exception:
                continue
        if self.font is None:
            self.font = pygame.font.Font(None, size)
        self.small = pygame.font.Font(None, max(12, int(self.cell_h * 0.62)))
        self.glyph_cache = {}

    def resize(self, w, h):
        ratio = 1.5 if self.sprite_mode else 1.9
        cell_w = max(6, min(w // NUMCOLS, int((h // NUMLINES) / ratio)))
        if cell_w == self.cell_w:
            return
        self.cell_w = cell_w
        self.cell_h = self._cell_height(cell_w)
        self._load_fonts()
        self._build_sprites()

    # -- glyphs ------------------------------------------------------------

    def glyph(self, ch, color):
        """Render-and-cache one character.  Rendering every glyph every frame
        is the obvious way to write this and is far too slow at 80x24x60fps.

        Control characters are replaced rather than passed through: pygame
        raises on some of them (font.render("") is "Text has zero width"),
        and a single bad character anywhere in a message would otherwise take
        down the whole frame.
        """
        if ch and (ord(ch) < 32 or ord(ch) == 127):
            ch = "?"
        key = (ch, color)
        surf = self.glyph_cache.get(key)
        if surf is None:
            surf = self.font.render(ch, True, color)
            self.glyph_cache[key] = surf
        return surf

    def blit_ch(self, ch, color, row, col, x_off=0, y_off=0):
        if ch == ' ':
            return
        surf = self.glyph(ch, color)
        x = x_off + col * self.cell_w + (self.cell_w - surf.get_width()) // 2
        y = y_off + row * self.cell_h + (self.cell_h - surf.get_height()) // 2
        self.screen_surf.blit(surf, (x, y))

    # -- the frame ---------------------------------------------------------

    def draw_frame(self):
        if self.headless:
            return
        game = self.game
        surf = self.screen_surf
        surf.fill(BG)

        w = self.cell_w * NUMCOLS
        h = self.cell_h * NUMLINES
        x_off = (surf.get_width() - w) // 2
        y_off = (surf.get_height() - h) // 2

        self._draw_message(x_off, y_off)
        self._draw_map(x_off, y_off)
        self._draw_status(x_off, y_off, h)
        if self.overlay is not None:
            self._draw_overlay()
        pygame.display.flip()

    def _draw_message(self, x_off, y_off):
        game = self.game
        text = game.msg_queue[0] if game.msg_queue else ""
        if text:
            color = FG_MSG
            for i, ch in enumerate(text[:NUMCOLS]):
                self.blit_ch(ch, color, 0, i, x_off, y_off)
            if len(game.msg_queue) > 1:
                more = "--More--"
                start = min(len(text) + 1, NUMCOLS - len(more))
                for i, ch in enumerate(more):
                    self.blit_ch(ch, FG_MORE, 0, start + i, x_off, y_off)

    # characters that sit ON the floor rather than being terrain -- these get
    # a ground tile drawn underneath so entities aren't floating in the void
    ENTITY_CHARS = set(PLAYER + GOLD + POTION + SCROLL + FOOD + WEAPON
                       + ARMOR + RING + STICK + AMULET + MAGIC + TRAP
                       + "ABCDEFGHIJKLMNOPQRSTUVWXYZ")

    def _draw_map_sprites(self, x_off, y_off):
        game = self.game
        scr = game.screen
        cw, chh = self.cell_w, self.cell_h
        surf = self.screen_surf
        floor_spr = self.sprites.get(FLOOR)
        pass_spr = self.sprites.get(PASSAGE)
        floor_dim = self.sprites_dim.get(FLOOR)
        pass_dim = self.sprites_dim.get(PASSAGE)

        for row in range(MAP_TOP, MAP_BOTTOM + 1):
            line = scr.ch[row]
            so_line = scr.so[row]
            y = y_off + row * chh
            for col in range(NUMCOLS):
                ch = line[col]
                if ch == ' ':
                    continue
                visible = cansee(game, row, col)
                sheet = self.sprites if visible else self.sprites_dim
                x = x_off + col * cw

                if ch in self.ENTITY_CHARS:
                    # ground first, then the thing standing on it
                    ground = (pass_spr if (game.flat(row, col) & F_PASS)
                              else floor_spr)
                    if not visible:
                        ground = (pass_dim if (game.flat(row, col) & F_PASS)
                                  else floor_dim)
                    if ground is not None:
                        surf.blit(ground, (x, y))

                spr = sheet.get(ch)
                if spr is None:
                    # no art for this character -- fall back to the glyph so
                    # nothing ever silently vanishes off the map
                    color = TILE_COLORS.get(ch, FG_DEFAULT)
                    if not visible:
                        color = _dim(color)
                    self.blit_ch(ch, color, row, col, x_off, y_off)
                    continue
                surf.blit(spr, (x, y))

                if so_line[col]:
                    # SEEMONST: a detected-but-unseen monster, shown highlighted
                    glow = pygame.Surface((cw, chh), pygame.SRCALPHA)
                    glow.fill((120, 80, 160, 70))
                    surf.blit(glow, (x, y))

    def _draw_map(self, x_off, y_off):
        if self.sprite_mode:
            self._draw_map_sprites(x_off, y_off)
            return
        game = self.game
        scr = game.screen
        hero = game.hero
        for row in range(MAP_TOP, MAP_BOTTOM + 1):
            line = scr.ch[row]
            so_line = scr.so[row]
            for col in range(NUMCOLS):
                ch = line[col]
                if ch == ' ':
                    continue
                if ch == PLAYER:
                    # a soft highlight behind the hero so he is findable
                    pygame.draw.rect(
                        self.screen_surf, HILITE,
                        pygame.Rect(x_off + col * self.cell_w,
                                    y_off + row * self.cell_h,
                                    self.cell_w, self.cell_h))
                    self.blit_ch(ch, TILE_COLORS[PLAYER], row, col, x_off, y_off)
                    continue
                if ch.isalpha() and ch.isupper():
                    color = _monster_color(ch)
                else:
                    color = TILE_COLORS.get(ch, FG_DEFAULT)
                # remembered-but-not-currently-visible tiles are dimmed.  This
                # is presentation only -- it reads from cansee(), the same
                # predicate the game logic uses, and changes no rules.
                if not (row == hero.y and col == hero.x):
                    if not cansee(game, row, col):
                        color = _dim(color)
                if so_line[col]:
                    color = (min(255, color[0] + 60), min(255, color[1] + 60),
                             min(255, color[2] + 60))
                self.blit_ch(ch, color, row, col, x_off, y_off)

    def _draw_status(self, x_off, y_off, h):
        game = self.game
        row = NUMLINES - 1
        pygame.draw.rect(self.screen_surf, BG_STATUS,
                         pygame.Rect(x_off, y_off + row * self.cell_h,
                                     self.cell_w * NUMCOLS, self.cell_h))
        arm = (game.cur_armor.o_arm if game.cur_armor is not None
               else game.pstats.s_arm)
        st = game.pstats
        text = ("Level: %d  Gold: %d  Hp: %d(%d)  Str: %d  Arm: %d  Exp: %d/%d  %s"
                % (game.level, game.purse, st.s_hpt, st.s_maxhp, st.s_str,
                   10 - arm, st.s_lvl, st.s_exp,
                   HUNGER_NAMES[game.hungry_state]))
        low = st.s_maxhp > 0 and st.s_hpt * 4 <= st.s_maxhp
        for i, ch in enumerate(text[:NUMCOLS]):
            color = FG_STATUS
            if low and 25 <= i < 25 + 14:
                color = FG_LOWHP
            self.blit_ch(ch, color, row, i, x_off, y_off)

    def _draw_overlay(self):
        surf = self.screen_surf
        lines = self.overlay
        pad = self.cell_w
        width = max([len(s) for s in lines] + [len(self.overlay_title), 30])
        box_w = min(surf.get_width() - 2 * pad, (width + 4) * self.cell_w)
        box_h = min(surf.get_height() - 2 * pad,
                    (len(lines) + 4) * self.cell_h)
        x = (surf.get_width() - box_w) // 2
        y = (surf.get_height() - box_h) // 2
        pygame.draw.rect(surf, (18, 20, 26), pygame.Rect(x, y, box_w, box_h))
        pygame.draw.rect(surf, (92, 100, 120),
                         pygame.Rect(x, y, box_w, box_h), 2)
        ty = y + self.cell_h // 2
        if self.overlay_title:
            t = self.font.render(self.overlay_title, True, FG_MORE)
            surf.blit(t, (x + self.cell_w, ty))
            ty += self.cell_h
        for line in lines:
            if ty + self.cell_h > y + box_h - self.cell_h:
                break
            t = self.font.render(line, True, FG_DEFAULT)
            surf.blit(t, (x + self.cell_w, ty))
            ty += self.cell_h
        t = self.small.render("-- press space --", True, FG_MORE)
        surf.blit(t, (x + self.cell_w, y + box_h - self.cell_h))

    # -- overlay control ---------------------------------------------------

    def show_overlay(self, lines, title=""):
        self.overlay = list(lines)
        self.overlay_title = title

    def clear_overlay(self):
        self.overlay = None
        self.overlay_title = ""


# ---------------------------------------------------------------------------
# The game loop and entry point.  Ported from main.c and command.c, with the
# blocking curses input replaced by a pygame event loop.
# ---------------------------------------------------------------------------

# rip.c:399 -- non-monster killers
KILL_NAMES = {
    'a': ("arrow", True),
    'b': ("bolt", True),
    'd': ("dart", True),
    'h': ("hypothermia", False),
    's': ("starvation", False),
}

# command.c:120 -- commands a repeat count applies to
COUNTABLE = set(".abhjklmnqrstuyzBCHIJKLNUY")

MOVE_KEYS = {
    'h': (0, -1), 'j': (1, 0), 'k': (-1, 0), 'l': (0, 1),
    'y': (-1, -1), 'u': (-1, 1), 'b': (1, -1), 'n': (1, 1),
}

HELP_LINES = [
    "?      this help              /      identify a character",
    "h j k l  move left/down/up/right     y u b n  move diagonally",
    "H J K L  run in a direction          Y U B N  run diagonally",
    ".      rest a turn            s      search for secret doors",
    ",      pick up something      d      drop something",
    "i      inventory              I      inventory one item",
    "q      quaff a potion         r      read a scroll",
    "e      eat food               z      zap a wand or staff",
    "w      wield a weapon         t      throw something",
    "W      wear armor            T      take armor off",
    "P      put on a ring          R      remove a ring",
    ">      go down a staircase    <      go up a staircase",
    "^      identify a trap        D      list discoveries",
    "Q      quit                   ESC    cancel a command",
]


def killname(monst, doart):
    """rip.c:394 -- what killed the hero."""
    if isupper_ch(monst):
        sp = MONSTERS[ord(monst) - ord('A')]['name']
        article = True
    else:
        entry = KILL_NAMES.get(monst)
        if entry is None:
            return "Wally the Wonder Badger"
        sp, article = entry
    if doart and article:
        return "a%s %s" % (vowelstr(sp), sp)
    return sp


def death(game, monst):
    """rip.c:232 -- the hero dies."""
    if not game.playing:
        return
    game.purse -= game.purse // 10
    game.playing = False
    game.win = False
    game.death_reason = killname(monst, True)
    game.pstats.s_hpt = 0


def total_winner(game):
    """rip.c -- escaped the dungeon with the Amulet."""
    game.playing = False
    game.win = True
    game.death_reason = None


def tombstone_lines(game):
    """rip.c -- the RIP screen, as text lines."""
    st = game.pstats
    if game.win:
        return [
            "",
            "    @   @  @  @@@   @@@  @   @  @@@  @@@@   @",
            "    @   @  @  @  @ @   @ @@ @@   @   @   @  @",
            "    @ @ @  @  @  @ @   @ @ @ @   @   @@@@   @",
            "    @@ @@  @  @  @ @   @ @   @   @   @   @   ",
            "    @   @  @  @@@   @@@  @   @  @@@  @   @  @",
            "",
            "  You escaped the Dungeons of Doom with the Amulet of Yendor",
            "  and %d pieces of gold." % game.purse,
            "",
            "  Level %d with %d experience." % (st.s_lvl, st.s_exp),
        ]
    return [
        "",
        "                    ----------",
        "                   /          \\",
        "                  /    REST    \\",
        "                 /      IN      \\",
        "                /     PEACE      \\",
        "               /                  \\",
        "               |   %-14s |" % game.whoami[:14],
        "               |  killed by       |",
        "               |  %-15s |" % (game.death_reason or "?")[:15],
        "               |                  |",
        "               |  %-15s |" % ("%d gold" % game.purse),
        "               *|   *  *  *    *   | *",
        "      __________)/\\\\__//(\\/(/\\)/\\//\\/|_)_______",
        "",
        "  Killed on level %d with %d gold." % (game.level, game.purse),
    ]


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

class GameLoop(object):

    def __init__(self, game, renderer):
        self.game = game
        self.renderer = renderer
        # Pending input state.  The C blocks in readchar() inside get_item(),
        # get_dir() and gethand(); a pygame loop cannot block, so a command
        # that needs a follow-up key parks a continuation here instead.
        self.pending = None         # (kind, callback, extra)
        self.moves_left = 0         # remaining iterations of command()'s ntimes loop
        self.count = 0              # repeat-count prefix
        self.countch = None
        self.collecting_count = False
        self.again = False
        self.last_dir = None
        self.text_buf = ""

    # -- input -------------------------------------------------------------

    def feed(self, ch):
        """Feed one character in.  Returns True if a game turn was consumed."""
        game = self.game
        if not game.playing:
            return False

        if self.renderer is not None and self.renderer.overlay is not None:
            self.renderer.clear_overlay()
            return False

        if len(game.msg_queue) > 1:
            game.msg_queue.pop(0)
            return False

        if self.pending is not None:
            kind, cb = self.pending[0], self.pending[1]
            if ch == chr(ESCAPE):
                self.pending = None
                self.text_buf = ""
                if self.renderer is not None:
                    self.renderer.clear_overlay()
                game.after = False
                msg(game, "")
                return False
            if kind == 'item':
                type_ch = self.pending[2]
                if ch == '*':
                    lines = inventory(game, game.pack, type_ch)
                    if lines and self.renderer is not None:
                        self.renderer.show_overlay(lines, "Inventory")
                    return False
                obj = None
                for o in game.pack:
                    if o.o_packch == ch:
                        obj = o
                        break
                if obj is None:
                    msg(game, "'%s' is not a valid item" % unctrl(ch))
                    return False
                self.pending = None
                return self.finish(cb, obj)
            if kind == 'dir':
                if ch not in MOVE_KEYS:
                    low = ch.lower()
                    if low not in MOVE_KEYS:
                        msg(game, "which direction?")
                        return False
                    ch = low
                dy, dx = MOVE_KEYS[ch]
                game.delta.y = dy
                game.delta.x = dx
                game.dir_ch = ch
                if on(game.player, ISHUH) and rnd(5) == 0:
                    while True:
                        game.delta.y = rnd(3) - 1
                        game.delta.x = rnd(3) - 1
                        if game.delta.y or game.delta.x:
                            break
                self.pending = None
                return self.finish(cb, (game.delta.y, game.delta.x))
            if kind == 'hand':
                low = ch.lower()
                if low not in ('l', 'r'):
                    msg(game, "please type L or R")
                    return False
                self.pending = None
                return self.finish(cb, LEFT if low == 'l' else RIGHT)
            if kind == 'confirm':
                self.pending = None
                return self.finish(cb, ch.lower() == 'y')
            if kind == 'symbol':
                self.pending = None
                cb(ch)
                return False
            if kind == 'option':
                if ch == ' ':
                    self.pending = None
                    if self.renderer is not None:
                        self.renderer.clear_overlay()
                    return False
                cb(ch)
                return False
            if kind == 'text':
                # a free-text prompt, for naming an unidentified item.
                # chr(13)/chr(10) are Enter, chr(8) is Backspace.
                if ch in (chr(13), chr(10)):
                    name = self.text_buf
                    self.text_buf = ""
                    self.pending = None
                    if name:
                        cb(name)
                    return False
                if ch == chr(8):
                    self.text_buf = self.text_buf[:-1]
                else:
                    self.text_buf += ch
                msg(game, "call it: %s" % self.text_buf)
                return False
            self.pending = None
            return False

        return self.turn(ch)

    def ask_item(self, purpose, type_ch, cb):
        msg(self.game, "which object do you want to %s? (* for list): " % purpose)
        self.pending = ('item', cb, type_ch)

    def ask_dir(self, cb):
        msg(self.game, "which direction? ")
        self.pending = ('dir', cb, None)

    def ask_hand(self, cb):
        msg(self.game, "left hand or right hand? ")
        self.pending = ('hand', cb, None)

    def ask_confirm(self, text, cb):
        msg(self.game, text)
        self.pending = ('confirm', cb, None)

    def finish(self, cb, value):
        """Run a parked continuation, then close out the turn it belongs to.

        A continuation may itself park another prompt -- `z` and `t` ask for
        a direction and THEN an item.  Closing the turn here in that case
        would charge two turns for one command, giving every monster a free
        move and burning a turn off every active fuse.
        """
        game = self.game
        game.after = True
        cb(value)
        if self.pending is not None:
            return False            # another prompt was parked; not done yet
        self.consume_pending_whatis()
        if self.pending is not None:
            return False            # now waiting for the identify target
        return self.end_turn()

    def consume_pending_whatis(self):
        """A scroll of identify asked for something to identify."""
        game = self.game
        if game.pending_whatis is None:
            return
        type_ch = game.pending_whatis
        game.pending_whatis = None
        if not game.pack:
            msg(game, "you don't have anything in your pack to identify")
            return
        self.ask_item("identify", type_ch,
                      lambda o: identify_obj(game, o))

    # -- the turn ----------------------------------------------------------

    def end_command(self):
        """command.c:447 -- the tail of command(), run ONCE per command call.

        The after-daemons are outside the ntimes loop in the C, so a hasted
        player gets two actions against one round of monster movement -- that
        is what haste actually buys.  The ring effects below were missing
        entirely: the ring of searching auto-searches every turn, and the ring
        of teleportation is what makes that ring cursed.
        """
        game = self.game
        do_daemons(game, AFTER)
        do_fuses(game, AFTER)
        if game.is_ring(LEFT, R_SEARCH):
            search(game)
        elif game.is_ring(LEFT, R_TELEPORT) and rnd(50) == 0:
            teleport(game)
        if game.is_ring(RIGHT, R_SEARCH):
            search(game)
        elif game.is_ring(RIGHT, R_TELEPORT) and rnd(50) == 0:
            teleport(game)
        if game.pstats.s_hpt <= 0 and game.playing:
            death(game, 'h')
        game.turns += 1
        if game.playing:
            look(game, True)

    def end_turn(self):
        """Close out a command that had parked on a follow-up keypress."""
        game = self.game
        if game.take:
            pick_up(game, game.take)
            game.take = 0
        if not game.running:
            game.door_stop = False
        if not game.after:
            self.moves_left += 1        # command.c:444  if (!after) ntimes++
        self.moves_left -= 1
        if self.moves_left <= 0:
            self.end_command()
        return True

    def turn(self, ch):
        """command.c:24 -- process one user command.

        One keypress is one iteration of the C's `while (ntimes--)` loop.  The
        before-daemons fire when a fresh command() call begins; the after
        half fires when the last iteration is spent.
        """
        game = self.game

        if self.moves_left <= 0:
            do_daemons(game, BEFORE)
            do_fuses(game, BEFORE)
            self.moves_left = 2 if on(game.player, ISHASTE) else 1

        if not game.playing:
            return False
        if game.has_hit:
            endmsg(game)
            game.has_hit = False
        look(game, True)
        if not game.running:
            game.door_stop = False
        game.take = 0
        game.after = True

        if game.no_command:
            game.no_command -= 1
            if game.no_command == 0:
                game.player.t_flags |= ISRUN
                msg(game, "you can move again")
            c = '.'
        elif self.collecting_count:
            # command.c:101 -- the C sits in `while (isdigit(ch))` reading
            # more characters.  An event loop can't block, so the digit state
            # persists across keypresses instead.
            if ch.isdigit():
                self.count = min(255, self.count * 10 + int(ch))
                game.after = False
                return False
            self.collecting_count = False
            self.countch = ch
            if ch not in COUNTABLE:
                self.count = 0          # a count makes no sense for this one
            c = ch
        elif self.count and not game.running:
            c = self.countch
        else:
            c = ch
            if c.isdigit():
                self.count = int(c)
                self.collecting_count = True
                game.after = False
                return False

        if self.count and not game.running:
            self.count -= 1

        # command.c:145 -- remember the command for `a` (again)
        if (c != 'a' and c != chr(ESCAPE)
                and not (game.running or self.count or game.to_death)):
            game.l_last_comm = game.last_comm
            game.l_last_dir = game.last_dir
            game.l_last_pick = game.last_pick
            game.last_comm = c
            game.last_dir = ''
            game.last_pick = None

        self.dispatch(c)
        if self.pending is not None:
            return False                # waiting on a follow-up key

        return self.end_turn()

    def dispatch(self, ch):
        """command.c:153 -- the command switch."""
        game = self.game
        r = self.renderer

        if ch in MOVE_KEYS:
            dy, dx = MOVE_KEYS[ch]
            do_move(game, dy, dx)
            return
        if ch in "HJKLYUBN":
            low = ch.lower()
            do_run(game, low)
            dy, dx = MOVE_KEYS[low]
            do_move(game, dy, dx)
            return
        if len(ch) == 1 and 1 <= ord(ch) <= 26:
            # control-letter: run, but stop at doors.  command.c:203
            low = chr(ord(ch) - 1 + ord('a'))
            if low in MOVE_KEYS:
                if not on(game.player, ISBLIND):
                    game.door_stop = True
                    game.firstmove = True
                do_run(game, low)
                dy, dx = MOVE_KEYS[low]
                do_move(game, dy, dx)
                return

        if ch == ',':
            obj = find_obj(game, game.hero.y, game.hero.x)
            if obj is not None:
                if on(game.player, ISLEVIT):
                    msg(game, "you can't reach the ground")
                else:
                    pick_up(game, obj.o_type)
            else:
                if not game.terse:
                    addmsg(game, "there is ")
                addmsg(game, "nothing here")
                if not game.terse:
                    addmsg(game, " to pick up")
                endmsg(game)
        elif ch == '.':
            pass                                        # rest
        elif ch == 'q':
            self.ask_item("quaff", POTION, lambda o: quaff(game, o))
        elif ch == 'r':
            self.ask_item("read", SCROLL, lambda o: read_scroll(game, o))
        elif ch == 'e':
            self.ask_item("eat", FOOD, lambda o: eat(game, o))
        elif ch == 'w':
            self.ask_item("wield", WEAPON, lambda o: wield(game, o))
        elif ch == 'W':
            self.ask_item("wear", ARMOR, lambda o: wear(game, o))
        elif ch == 'T':
            take_off(game)
        elif ch == 'P':
            self.ask_item("put on", RING, self._put_on_ring)
        elif ch == 'R':
            if game.cur_ring[LEFT] is not None and game.cur_ring[RIGHT] is not None:
                self.ask_hand(lambda hand: ring_off(game, hand))
            else:
                ring_off(game, None)
        elif ch == 'd':
            self.ask_item("drop", 0, lambda o: drop(game, o))
        elif ch == 'z':
            self.ask_dir(self._zap_dir)
        elif ch == 't':
            self.ask_dir(self._throw_dir)
        elif ch == 's':
            search(game)
        elif ch == '>':
            game.after = False
            d_level(game)
        elif ch == '<':
            game.after = False
            u_level(game)
        elif ch == 'i':
            game.after = False
            lines = inventory(game, game.pack, 0)
            if lines and r is not None:
                r.show_overlay(lines, "Inventory")
        elif ch == 'I':
            # pack.c:352 -- picky_inven(): describe one item
            game.after = False
            if not game.pack:
                msg(game, "you aren't carrying anything")
            elif len(game.pack) == 1:
                msg(game, "a) %s" % inv_name(game, game.pack[0], False))
            else:
                self.pending = ('symbol', self._picky_inven, None)
                msg(game, "which item do you wish to inventory: ")
        elif ch == 'D':
            game.after = False
            lines = []
            for t in (POTION, SCROLL, RING, STICK):
                lines.extend(print_disc(game, t))
                lines.append("")
            if r is not None:
                r.show_overlay(lines, "Discoveries")
        elif ch == '?':
            game.after = False
            if r is not None:
                r.show_overlay(HELP_LINES, "Commands")
        elif ch == '^':
            game.after = False
            self.ask_dir(self._trap_id)
        elif ch == 'Q':
            game.after = False
            self.ask_confirm("really quit? (y/n)", self._really_quit)
        elif ch == ')':
            game.after = False
            self._current(game.cur_weapon, "wielding")
        elif ch == ']':
            game.after = False
            self._current(game.cur_armor, "wearing")
        elif ch == '=':
            game.after = False
            self._current(game.cur_ring[LEFT], "wearing (left)")
            self._current(game.cur_ring[RIGHT], "wearing (right)")
        elif ch == 'v':
            game.after = False
            msg(game, "version %s (pygame port)" % RELEASE)
        elif ch in ('f', 'F'):
            # command.c:222 -- fight an adjacent monster, F to the death
            if ch == 'F':
                game.kamikaze = True
            self.ask_dir(self._fight_dir)
        elif ch == 'a':
            # command.c:250 -- repeat the last command
            if not game.last_comm or game.last_comm == ' ':
                msg(game, "you haven't typed a command yet")
                game.after = False
            else:
                self.again = True
                self.dispatch(game.last_comm)
                self.again = False
        elif ch == 'c':
            game.after = False
            self.ask_item("call", CALLABLE, self._call_item)
        elif ch == '/':
            game.after = False
            self.pending = ('symbol', self._identify_symbol, None)
            msg(game, "what do you want identified? ")
        elif ch == 'm':
            # command.c:345 -- move onto something without picking it up
            game.move_on = True
            self.ask_dir(self._move_on_dir)
        elif ch == '@':
            game.after = False
            self._status_msg()
        elif ch == 'o':
            game.after = False
            if r is not None:
                r.show_overlay(self._option_lines(), "Options")
            self.pending = ('option', self._toggle_option, None)
        elif ch == chr(ESCAPE):
            game.door_stop = False
            game.count = 0
            game.after = False
        else:
            # command.c:illcom
            game.after = False
            game.count = 0
            msg(game, "illegal command '%s'" % unctrl(ch))

    # -- command continuations --------------------------------------------

    def _put_on_ring(self, obj):
        """rings.c:41 -- the C asks which hand ONLY when both are free."""
        game = self.game
        if obj is None:
            return
        if obj.o_type != RING:
            ring_on(game, obj, None)        # it prints the right complaint
            return
        if is_current(game, obj):
            return
        if game.cur_ring[LEFT] is None and game.cur_ring[RIGHT] is None:
            self.ask_hand(lambda hand: ring_on(game, obj, hand))
            return
        ring_on(game, obj, None)            # exactly one hand free, or neither

    def _zap_dir(self, _delta):
        self.ask_item("zap with", STICK, lambda o: do_zap(self.game, o))

    def _throw_dir(self, delta):
        dy, dx = delta
        self.ask_item("throw", WEAPON,
                      lambda o: missile(self.game, dy, dx, o))

    def _trap_id(self, _delta):
        game = self.game
        y = game.hero.y + game.delta.y
        x = game.hero.x + game.delta.x
        if not game.in_bounds(y, x):
            msg(game, "no trap there")
            return
        if game.chat(y, x) != TRAP:
            msg(game, "no trap there")
        elif on(game.player, ISHALU):
            msg(game, TRAP_NAMES[rnd(NTRAPS)])
        else:
            fl = game.flat(y, x)
            msg(game, TRAP_NAMES[fl & F_TMASK])
            game.set_flat(y, x, fl | F_SEEN)

    def _really_quit(self, yes):
        if yes:
            self.game.playing = False
            self.game.win = False
            self.game.death_reason = "quitting"

    def _fight_dir(self, delta):
        """command.c:222 -- lock onto an adjacent monster and keep swinging."""
        game = self.game
        y = game.hero.y + game.delta.y
        x = game.hero.x + game.delta.x
        if not game.in_bounds(y, x):
            msg(game, "no monster there")
            game.after = False
            game.kamikaze = False
            return
        mp = game.moat(y, x)
        if mp is None or (not see_monst(game, mp)
                          and not on(game.player, SEEMONST)):
            if not game.terse:
                addmsg(game, "I see ")
            msg(game, "no monster there")
            game.after = False
            game.kamikaze = False
        elif diag_ok(game, game.hero, Coord(x, y)):
            game.to_death = True
            game.max_hit = 0
            mp.t_flags |= ISTARGET
            game.runch = game.dir_ch
            do_move(game, game.delta.y, game.delta.x)

    def _move_on_dir(self, delta):
        game = self.game
        do_move(game, game.delta.y, game.delta.x)
        game.move_on = False

    def _call_item(self, obj):
        game = self.game
        if obj is None:
            return
        self.pending = ('text', lambda t: call_it(game, obj, t), "")
        msg(game, "what do you want to call it? ")

    def _identify_symbol(self, ch):
        """command.c -- identify() : explain a map character."""
        game = self.game
        if isupper_ch(ch):
            msg(game, "%s: %s" % (ch, MONSTERS[ord(ch) - ord('A')]['name']))
            return
        names = {
            PASSAGE: "passage", DOOR: "door", FLOOR: "room floor",
            PLAYER: "you", TRAP: "trap", STAIRS: "a staircase",
            GOLD: "gold", POTION: "potion", SCROLL: "scroll",
            FOOD: "food", WEAPON: "weapon", ARMOR: "armor",
            AMULET: "the Amulet of Yendor", RING: "ring", STICK: "wand or staff",
            MAGIC: "magic", VWALL: "wall of a room", HWALL: "wall of a room",
            ' ': "solid rock",
        }
        msg(game, "'%s': %s" % (unctrl(ch), names.get(ch, "unknown character")))

    def _picky_inven(self, ch):
        game = self.game
        for obj in game.pack:
            if obj.o_packch == ch:
                msg(game, "%c) %s" % (ch, inv_name(game, obj, False)))
                return
        msg(game, "'%s' not in pack" % unctrl(ch))

    def _status_msg(self):
        game = self.game
        arm = (game.cur_armor.o_arm if game.cur_armor is not None
               else game.pstats.s_arm)
        st = game.pstats
        msg(game, "Level: %d  Gold: %d  Hp: %d(%d)  Str: %d  Arm: %d  Exp: %d/%d %s"
            % (game.level, game.purse, st.s_hpt, st.s_maxhp, st.s_str,
               10 - arm, st.s_lvl, st.s_exp, HUNGER_NAMES[game.hungry_state]))

    OPTIONS = (('t', 'terse', "terse messages"),
               ('j', 'jump', "jump (skip run animation)"),
               ('f', 'see_floor', "show the floor in dark rooms"),
               ('p', 'passgo', "follow corridors around corners"),
               ('g', '@sprites', "graphics (off = original characters)"))

    def _option_value(self, attr):
        if attr == '@sprites':
            return self.renderer is not None and self.renderer.sprite_mode
        return getattr(self.game, attr)

    def _option_lines(self):
        out = ["press the letter to toggle, space to close", ""]
        for key, attr, label in self.OPTIONS:
            out.append("  %s)  %-34s %s"
                       % (key, label, "on" if self._option_value(attr) else "off"))
        return out

    def _toggle_option(self, ch):
        game = self.game
        for key, attr, _label in self.OPTIONS:
            if ch != key:
                continue
            if attr == '@sprites':
                if self.renderer is not None:
                    self.renderer.set_sprite_mode(not self.renderer.sprite_mode)
            else:
                setattr(game, attr, not getattr(game, attr))
            break
        if self.renderer is not None:
            self.renderer.show_overlay(self._option_lines(), "Options")

    def _current(self, cur, how):
        game = self.game
        if cur is not None:
            msg(game, "you are %s %c) %s"
                % (how, cur.o_packch, inv_name(game, cur, True)))
        else:
            msg(game, "you are %s nothing" % how)

    # -- running -----------------------------------------------------------

    def auto_step(self):
        """Continue a run or a repeat count without waiting for a key."""
        game = self.game
        if not game.playing or self.pending is not None:
            return False
        if game.no_command:
            return self.turn('.')
        if game.running:
            return self.turn(game.runch)
        return False


# ---------------------------------------------------------------------------
# Setting up a game
# ---------------------------------------------------------------------------

def new_game(seed=None, headless=False):
    """main.c:107 -- build a game and dig the first level."""
    game = Game(seed)
    game.headless = headless
    game.screen = Screen()
    game.detected_magic = []
    game.detected_food = []
    game.bolt_trail = []
    game.pending_whatis = None
    game.things = []
    # fight.c mutates the flytrap's damage string in the global monster table.
    # Faithful to the C, which only ever has one game per process -- but the
    # selftest builds many, so reset it or an inflated flytrap leaks forward.
    MONSTERS[ord('F') - ord('A')]['dmg'] = "000x0"
    # weapons.c: weap_info has a 10th row for FLAME (dragon breath/bolts)
    # whose name is written at runtime by fire_bolt.  extern.c:307
    game.weap_names = [w['name'] for w in WEAPONS] + ["flame"]

    init_probs(game)
    init_names(game)
    init_colors(game)
    init_stones(game)
    init_materials(game)
    init_player(game)

    new_level(game)

    start_daemon(game, runners_daemon, 0, AFTER)
    start_daemon(game, doctor, 0, AFTER)
    fuse(game, swander, 0, spread(70), AFTER)           # WANDERTIME
    start_daemon(game, stomach, 0, AFTER)
    return game


# ---------------------------------------------------------------------------
# Key translation
# ---------------------------------------------------------------------------

ARROW_KEYS = {}


def _keypad(n):
    """pygame 2 renamed K_KP1 to K_KP_1 and kept the old name as an alias.
    Accept whichever this pygame provides so keypad movement can't break
    startup on a build that has dropped the alias."""
    return getattr(pygame, "K_KP_%d" % n, None) or getattr(pygame, "K_KP%d" % n, None)


def _init_arrow_keys():
    ARROW_KEYS.update({
        pygame.K_LEFT: 'h', pygame.K_DOWN: 'j', pygame.K_UP: 'k',
        pygame.K_RIGHT: 'l',
        pygame.K_ESCAPE: chr(ESCAPE),
    })
    for n, ch in ((1, 'b'), (2, 'j'), (3, 'n'), (4, 'h'), (5, '.'),
                  (6, 'l'), (7, 'y'), (8, 'k'), (9, 'u')):
        key = _keypad(n)
        if key is not None:
            ARROW_KEYS[key] = ch


def event_to_char(event):
    if event.key in ARROW_KEYS:
        ch = ARROW_KEYS[event.key]
        if event.mod & pygame.KMOD_SHIFT and ch in MOVE_KEYS:
            return ch.upper()
        return ch
    # command.c:203 -- ^H ^J ^K ^L ^Y ^U ^B ^N run until something interesting.
    # These are control characters, so they never appear in event.unicode as
    # printable text and were previously dropped entirely.
    if event.mod & pygame.KMOD_CTRL:
        name = pygame.key.name(event.key)
        if len(name) == 1 and name.lower() in "hjklyubn":
            return chr(ord(name.lower()) - ord('a') + 1)
    # Enter and Backspace are needed by the free-text "call it" prompt and
    # are below the printable range, so they need passing through explicitly.
    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return chr(13)
    if event.key == pygame.K_BACKSPACE:
        return chr(8)
    if event.unicode and 32 <= ord(event.unicode[0]) < 127:
        return event.unicode[0]
    return None


# ---------------------------------------------------------------------------
# Self test
# ---------------------------------------------------------------------------

SELFTEST_KEYS = "hjklyubn.hjkl,siqrewWTPRdzt><s.hjkl"


def selftest(turns, seed):
    """Drive the game headlessly with pseudo-random input.

    This is the harness the port was debugged against: it exercises level
    generation, movement, combat, item use and the daemon scheduler without a
    display, and turns any exception into a nonzero exit.
    """
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((320, 240))
    _init_arrow_keys()

    game = new_game(seed, headless=True)
    loop = GameLoop(game, None)

    rng = random.Random(seed if seed is not None else 12345)
    levels_seen = set()
    deaths = 0
    done = 0
    while done < turns:
        if not game.playing:
            # A random-walking hero dies fast, which would leave the deeper
            # levels untested.  Start a fresh game and keep going rather than
            # softening the rules to keep one hero alive.
            deaths += 1
            game = new_game(None, headless=True)
            loop = GameLoop(game, None)
        # drain any pending --More--
        while len(game.msg_queue) > 1:
            game.msg_queue.pop(0)
        if loop.pending is not None:
            kind = loop.pending[0]
            if kind == 'item':
                ch = (rng.choice(game.pack).o_packch if game.pack
                      else chr(ESCAPE))
            elif kind == 'dir':
                ch = rng.choice("hjklyubn")
            elif kind == 'hand':
                ch = rng.choice("lr")
            elif kind == 'confirm':
                ch = 'n'
            else:
                ch = chr(ESCAPE)
        else:
            ch = rng.choice(SELFTEST_KEYS)
        loop.feed(ch)
        levels_seen.add(game.level)
        done += 1
        # Force progress deeper on a short cadence.  A random walker almost
        # never finds the stairs, so without this the soak would only ever
        # test level 1 -- and maze rooms, the deep monster tables and the
        # Amulet at level 26 would go unexercised.
        if done % 40 == 0 and game.playing:
            game.level += 1
            new_level(game)

    print("selftest ok: %d turns, seed=%s, deepest level=%d, levels=%s, deaths=%d"
          % (done, seed, max(levels_seen), sorted(levels_seen)[:14], deaths))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def play(seed, sprites=True):
    pygame.init()
    _init_arrow_keys()
    game = new_game(seed)
    renderer = Renderer(game, sprites=sprites)
    game.renderer = renderer
    loop = GameLoop(game, renderer)

    msg(game, "Hello %s, welcome to the Dungeons of Doom.  Press ? for help."
        % game.whoami)
    look(game, True)

    clock = pygame.time.Clock()
    ended_shown = False
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                renderer.resize(event.w, event.h)
            elif event.type == pygame.KEYDOWN:
                if not game.playing:
                    if ended_shown:
                        running = False
                    continue
                ch = event_to_char(event)
                if ch is not None:
                    loop.feed(ch)

        if game.playing and loop.pending is None and game.running:
            loop.auto_step()

        if not game.playing and not ended_shown:
            renderer.show_overlay(tombstone_lines(game),
                                  "You win!" if game.win else "You died")
            ended_shown = True

        renderer.draw_frame()
        clock.tick(30)

    pygame.quit()
    return 0


def main(argv):
    parser = argparse.ArgumentParser(
        description="Rogue 5.4.5, ported to Python and pygame.")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed the dungeon for a reproducible game")
    parser.add_argument("--selftest", type=int, metavar="N", default=None,
                        help="run N turns headlessly and exit nonzero on error")
    parser.add_argument("--ascii", action="store_true",
                        help="draw the original character grid instead of sprites")
    args = parser.parse_args(argv)

    validate_sprites()      # fail loudly on bad art rather than blank tiles

    try:
        if args.selftest is not None:
            return selftest(args.selftest, args.seed)
        return play(args.seed, sprites=not args.ascii)
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
