# Copyright 2008, Aren Olson <reacocard@gmail.com>. All rights reserved.

# Redistribution and use in source and binary forms, with or without modification, are
# permitted provided that the following conditions are met:

#    1. Redistributions of source code must retain the above copyright notice, this list of
#       conditions and the following disclaimer.

#    2. Redistributions in binary form must reproduce the above copyright notice, this list
#       of conditions and the following disclaimer in the documentation and/or other materials
#       provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE ABOVE COPYRIGHT HOLDER ``AS IS'' AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE ABOVE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those of the
# authors and should not be interpreted as representing official policies, either expressed
# or implied, of the above copyright holder.

import sys, os, mmap, time

mapping = [0,1,2,3,4,5,6,7,8]

# magic DB version number
MAGIC = 1413695500


TAGS = [
    'artist', 
    'album', 
    'genre', 
    'title', 
    'filename', 
    'composer', 
    'comment', 
    'albumartist', 
    'grouping', 

    'year', # just year, not date?
    'discnumber', 
    'tracknumber', 
    'bitrate', 
    'length', # in milliseconds
    'playcount', 
    'rating', 
    'playtime', 
    'lastplayed', 
    'commitid', # how is this calculated?
    'mtime'
    ]
TAG_COUNT = 20

FLAGS = {
        1: "DELETED",
        2: "DIRCACHE",
        4: "DIRTYNUM",
        8: "TRKNUMGEN",
        16: "RESURRECTED"
        }
SGALF = dict([ (v,k) for k,v in FLAGS.iteritems() ])

def to_int(s):
    total = 0
    for c in s[::-1]: 
        total = total*256
        total += ord(c)
    return total

def to_str(i, n=0):
    s = ""
    while i > 0:
        s += chr(i & 0xff)
        i = i >> 8
    if n:
        if len(s) < n:
            s = s + (n - len(s))*chr(0) 
    return s

def mtime_to_unix(mtime):
    date = mtime >> 16
    tim = mtime & 0x0000FFFF
    year = ((date >> 9) & 0x7F) + 1980
    month = (date >> 5) & 0x0F
    day = date & 0x1F
    hour = (tim >> 11) & 0x1F
    minute = (tim >> 5) & 0x3F
    second = tim & 0x1F
    print (year, month, day, hour, minute, second)
    t = time.mktime((year, month, day, hour, minute, second, -1, -1, -1))
    return t

def unix_to_mtime(unix):
    year, month, day, hour, minute, second = time.localtime(unix)[:-3]
    year = year - 1980
    date = 0
    date |= (year << 9)
    date |= (month << 5)
    date |= day
    tim = 0
    tim |= (hour << 11)
    tim |= (minute << 5)
    tim |= second
    total = (date << 16) | tim
    return total




class Database(list):
    def __init__(self, dir):
        list.__init__(self)
        self.magic = MAGIC
        self.serial = 0 #lastplayed
        self.commitid = 0
        self.dirty = 0
        self.dir = dir

    def parse(self):
        del self[:] # clear any existing data

        files = [ open(os.path.join(self.dir, "database_%s.tcd"%x), "rb+") \
                for x in [0,1,2,3,4,5,6,7,8,"idx"] ]
        mmaps = [ mmap.mmap(f.fileno(), 0) for f in files ]
        idx = mmaps[9]

        self.magic = to_int(idx[0:4]) 
        if self.magic != MAGIC:
            raise ValueError, "Incompatible DB version"
        entry_count = to_int(idx[8:12])
        self.serial = to_int(idx[12:16])
        self.commitid = to_int(idx[16:20])
        self.dirty = to_int(idx[20:24])
        if self.dirty != 0:
            print "WARNING: DB may be corrupt"
 
        for n in range(entry_count):
            e = Entry()
            e.index = n
            offset = 24+n*84
            for n2 in range(9):
                e[n2] = to_int(idx[offset:offset+4])
                offset += 4
            for n2 in range(9, 20):
                e[TAGS[n2]] = to_int(idx[offset:offset+4])
                offset += 4
            flags = to_int(idx[offset:offset+4])
            e.flags = [ FLAGS[flag] for flag in FLAGS if flags | flag == flags ]

            self.append(e)

        for e in self:
            if FLAGS[1] in e.flags:
                continue # Don't restore data on deleted files
            for n in range(9):
                tname = TAGS[n]
                offset = e[n]
                l = to_int(mmaps[n][offset:offset+2])
                e[tname] = mmaps[n][offset+4:offset+4+l].split(chr(0))[0]
                del e[n]

    # WARNING: if this gets interrupted the DB will be left in an unusuable state
    def write(self):
        def skey(item):
            item = item.lower()
            if item.startswith("the "):
                item = item[4:]
            return item

        files = [ open(os.path.join(self.dir, "database_%s.tcd"%x), "wb+") \
                for x in [0,1,2,3,4,5,6,7,8,"idx"] ]
 
        # tag files
        for tn in range(9):
            f = files[tn]
            tname = TAGS[tn]

            #header
            f.write(to_str(self.magic, 4))
            f.write(to_str(0,4)) # placeholder until we know the full length
            f.write(to_str(0,4)) # placeholder until we know the full count
          
            if tn in [3,4]:
                tags = []
                for e in self:
                    if FLAGS[1] in e.flags:
                        continue # deleted tracks shouldn't contribute entries
                    tags.append((e[tname], e))
                tags.sort(key=lambda x: skey(x[0]))
                length = 0
                for tag, e in tags:
                    tag += chr(0) # strings must be null-terminated
                    if tn != 4:
                        # pad the string
                        if (len(tag)-4) % 8:
                            tag += "X" * (8 - ((len(tag)-4) % 8))
                    l = len(tag)
                    id = self.index(e)
                    f.write(to_str(l,2))
                    f.write(to_str(id,2))
                    f.write(tag)
                    e[tn] = 12 + length
                    length += 4 + l

            else:
                tags = {}
                for e in self:
                    if FLAGS[1] in e.flags:
                        continue # deleted tracks shouldn't contribute entries
                    if e[tname] in tags:
                        tags[e[tname]].append(e)
                    else:
                        tags[e[tname]] = [e]
                tagkeys = tags.keys()
                tagkeys.sort(key=skey)

                length = 0
                for tag in tagkeys:
                    rawtag = tag
                    tag += chr(0) # strings must be null-terminated
                    # pad the string
                    if (len(tag)-4) % 8:
                        tag += "X" * (8 - ((len(tag)-4) % 8))
                    l = len(tag)
                    id = 65535
                    f.write(to_str(l,2))
                    f.write(to_str(id,2))
                    f.write(tag)
                    for e in tags[rawtag]:
                        e[tn] = 12 + length
                    length += 4 + l
            
            # go back and fill in the header properly
            f.seek(4)
            f.write(to_str(length, 4))
            f.write(to_str(len(tags), 4))

        # master index
        f = files[9]
        f.write(to_str(self.magic,4))
        f.write(to_str(len(self)*84,4))
        f.write(to_str(len(self),4))
        f.write(to_str(self.serial, 4))
        self.commitid += 1
        f.write(to_str(self.commitid, 4))
        f.write(to_str(1,4)) # set dirty
        
        ids = mapping + TAGS[len(mapping):]
        for e in self:
            s = "".join([ to_str(e[x], 4) for x in ids ])
            raw_flags = e.get_raw_flags()
            s += to_str(raw_flags, 4)
            f.write(s)
            for i in mapping:
                del e[i]
    
        f.seek(20)
        f.write(to_str(0, 4)) #unmark dirty

        for f in files:
            f.close()

    def clean_up(self):
        to_del = []
        for e in self:
            if FLAGS[1] in e.flags: # deleted
                to_del.append(e)
            if FLAGS[16] in e.flags: # resurrected
                e.flags.remove(FLAGS[16]) 
            if FLAGS[4] in e.flags: # dirty
                e.flags.remove(FLAGS[4])
        for e in to_del:
            self.remove(e)
    
        
class Entry(dict):
    def __init__(self):
        dict.__init__(self)
        for t in TAGS[:9]:
            self[t] = "<Untagged>"
        for t in TAGS[9:]:
            self[t] = 0
        self.flags = []

    def get_raw_flags(self):
        raw_flags = 0
        for fl in SGALF:
            if fl in self.flags:
                raw_flags |= SGALF[fl]
        return raw_flags

    def flatten(self):
        ret = []
        for t in TAGS:
            ret.append(self[t])
        return ret


