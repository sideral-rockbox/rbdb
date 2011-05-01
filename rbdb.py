
import sys, os, mmap, time

mapping = [0,1,2,3,4,5,6,7,8]

# magic DB version number as of this writing (May 2011)
MAGIC = 0x5443480e

# tags are encoded in UTF-8
# text tags like artist are someitmes padded out with XXXXes, presumably 
#   for easy expansion (lengths padded to: 4+8*n)
# number tags are 0 for not given or undefined
TAGS = [
    # this first 9 are byte offsets for the entries in the separated indicies
    'artist', 
    'album', 
    'genre', 
    'title', 
    'filename', 
    'composer', 
    'comment', 
    'albumartist', 
    'grouping', 

    # the remainder are embedded in the main db
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
    'mtime',
    'lastoffset'
    ]
TAG_COUNT = 21

FLAGS = {
        1: "DELETED",
        2: "DIRCACHE",
        4: "DIRTYNUM",
        8: "TRKNUMGEN",
        16: "RESURRECTED"
        }

def to_int(s):
    total = 0
    for c in s[::-1]: 
        total = total*256
        total += ord(c)
    return total

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

def reprnonstr(s):
    if type(s) == str:
        return s
    else:
        return repr(s)

class TagfileEntry:
    def __init__(self):
        self.tag_length = None
        self.idx_id = None
        self.data = ""

    def __repr__(self):
        return "".join([reprnonstr(x) for x in (
               " Length: ", self.tag_length, "\n",\
               " Id:     ", self.idx_id, "\n",\
               " Data:   ", repr(self.data), "\n"
               )])

class IndexEntry:
    def __init__(self):
        self.tag_seek = [ 0 ] * TAG_COUNT
        self.flag = None
        self.index = None

    def get_flags(self):
        return [ FLAGS[flag] for flag in FLAGS if self.flag | flag == self.flag ]

    def get_idx(self):
        return ((self.flag >> 16) & 0x0000ffff)

    def __repr__(self):
        return "".join([reprnonstr(x) for x in (
               " Index:  ", self.index, "\n",\
               " Flags:  ", repr(self.get_flags()), "\n",\
               " Idx:    ", self.get_idx(), "\n",\
               " Tags:   ", self.tag_seek, "\n"\
               )])

class TagFile:
    def __init__(self):
        self.magic = None
        self.datasize = None
        self.entry_count = None
        self.entries = []

    def __repr__(self):
        return "".join([reprnonstr(x) for x in (
               "=Header:", "\n",\
               " Version: ", self.magic, "\n",\
               " Size:    ", self.datasize, "\n",\
               " Entries: ", self.entry_count, "\n", "\n",\
               "=Entry:\n",\
               "\n=Entry:\n".join([repr(e) for e in self.entries])
               )])

class IndexFile:
    def __init__(self):
        self.magic = None
        self.datasize = None
        self.entry_count = None

        self.serial = None
        self.commitid = None
        self.dirty = None

        self.entries = []

    def __repr__(self):

        return "".join([reprnonstr(x) for x in (
               "=Header:", "\n",\
               " Version: ", self.magic, "\n",\
               " Size:    ", self.datasize, "\n",\
               " Entries: ", self.entry_count, "\n",\
               " Serial:  ", self.serial, "\n",\
               " Commit:  ", self.commitid, "\n",\
               " Dirty:   ", self.dirty, "\n", "\n",\
               "=Entry:\n",\
               "\n=Entry:\n".join([repr(e) for e in self.entries])
               ) ])

def parse_tagfile(location):
    f = open(location, "rb+")
    m = mmap.mmap(f.fileno(), 0)
    tf = TagFile()

    tf.magic = to_int(m[0:4])
    tf.datasize = to_int(m[4:8])
    tf.entry_count = to_int(m[8:12])

    offset = 12
    for n in range(tf.entry_count):
        e = TagfileEntry()
        e.tag_length = to_int(m[offset:offset+4])
        e.idx_id = to_int(m[offset+4: offset+8])
        e.data = m[offset+8:offset+8+e.tag_length]
        offset += e.tag_length + 8
        tf.entries.append(e)

    return tf

def parse_indexfile(location):
    f = open(location, "rb+")
    m = mmap.mmap(f.fileno(), 0)
    tf = IndexFile()

    tf.magic = to_int(m[0:4])
    tf.datasize = to_int(m[4:8])
    tf.entry_count = to_int(m[8:12])

    tf.serial = to_int(m[12:16])
    tf.commitid = to_int(m[16:20])
    tf.dirty = to_int(m[20:24])

    for n in range(tf.entry_count):
        e = IndexEntry()
        e.index = n
        offset = 24+n*84
        for n2 in range(0, 20):
            e.tag_seek[n2] = to_int(m[offset:offset+4])
            offset += 4

        e.flag = to_int(m[offset:offset+4])
        tf.entries.append(e)

    return tf


if __name__ == '__main__':

    try:
        num = str(mapping[int(sys.argv[1])])
    except:
        num = "idx"

    filename = "database_%s.tcd"%num

    print "Reading DB ", filename
    print "File size: ", os.path.getsize(filename)
    
    if num == "idx":
        res = parse_indexfile(filename)
    else:
        res = parse_tagfile(filename)
    
    print res


