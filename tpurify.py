import struct
from math import ceil, floor
from shutil import copyfile
from os import remove
import argparse
import time

# command line argument parsing
parser = argparse.ArgumentParser(description="Purifies Terraria worlds.")
parser.add_argument('filename', metavar="C:/Users/User/Documents/My Games/Terraria/Worlds/world_name.wld", 
					type=str, help="path to the world file you want to purify")
parser.add_argument('-p', '--purify-hallow', dest='purifyHallow', action='store_true',
					help="remove all traces of the hallow as well")
args = parser.parse_args()

# copy the world file so we don't wreck the original if an error is thrown
src = args.filename
dst = src[0:-4]+'.cpy'
copyfile(src, dst)
file = open(dst, 'r+b')

# half these functions aren't actually used,
# but if you ever need em, they're here
class DataRead():
	def __init__(self, file):
		self.file = file
	def bool(self, read_len):
		# stored little-endian
		data = self.file.read(read_len)
		return [int(x, 2) for x in [format(y, '08b') for y in data]]
	def byte(self, read_len):
		# only datatype stored big-endian
		data = self.file.read(read_len)
		if read_len == 1:
			# if we're only reading one byte,
			# return an unsigned char instead of a byte array
			fmt = 'B'
			return struct.unpack(fmt, data)
		else:
			fmt = '>' + read_len + 's'
			return struct.unpack(fmt, data)
	def short(self, read_len):
		read_len *= 2
		data = self.file.read(read_len)
		fmt = '<' + str(int(read_len/2)) + 'H' # unsigned short
		return struct.unpack(fmt, data)
	def int(self, read_len):
		read_len *= 4
		data = self.file.read(read_len)
		fmt = '<' + str(int(read_len/4)) + 'i' # signed integer, see uint for unsigned
		return struct.unpack(fmt, data)
	def float(self, read_len):
		read_len *= 4
		data = self.file.read(read_len)
		fmt = '<' + str(int(read_len/4)) + 'f' # float
		return struct.unpack(fmt, data)
	def double(self, read_len):
		read_len *= 8
		data = self.file.read(read_len)
		fmt = '<' + str(int(read_len/8)) + 'd' # double
		return struct.unpack(fmt, data)
	def uint(self, read_len):
		read_len *= 4
		data = self.file.read(read_len)
		fmt = '<' + str(int(read_len/4)) + 'I' # unsigned int
		return struct.unpack(fmt, data)
	def int64(self, read_len):
		read_len *= 8
		data = self.file.read(read_len)
		fmt = '<' + str(int(read_len/8)) + 'Q' # unsigned long long (equal to int64)
		return struct.unpack(fmt, data)
	def ulong(self, read_len):
		read_len *= 4
		data = self.file.read(read_len)
		fmt = '<' + str(int(read_len/4)) + 'L' # unsigned long
		return struct.unpack(fmt, data)

reader = DataRead(file)

"""
WLD files have a list of pointers in the file header, 
with each pointer pointing to the start of thenext section of the file.
There are ten pointers in total.
The pointer order is:
World Header
World Tiles <---- we want to jump to here!
Chests
Signs
NPCs
Entities
Footer
Last three are unused
"""
file.seek(0x01A)
section_pointers = reader.int(10)

# tileframeimportant will be important for proper tile reading
# note: tileframeimportant as of fileversion 194 is 470 bits (59 bytes)
# this may change in the future, but this code can handle those changes
file.seek(0x042)
tfi_len = reader.short(1)[0]
tfi_len = ceil(tfi_len/8)

tileframeimportant = file.read(tfi_len)
tileframeimportant = [int(x) for x in tileframeimportant]
tileframeimportant = [format(x, '08b') for x in tileframeimportant]
tileframeimportant = [x[::-1] for x in tileframeimportant]
tileframeimportant = ''.join(tileframeimportant)

position = section_pointers[1]
file.seek(position)

"""
Massive thanks to http://ludwig.schafer.free.fr/ for this info!

We're now in the tile data section.
Tiles consist of 1 to 13 bytes of data. (info is only stored when needed)
Data is as follows:

+--------------------------------------------------------------------------------------------------------------+
| Order |        Name        |               Note               |                  Present if...               |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   |       Flags1       |              Flags.              |   Always present, might be the only byte.    |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   |       Flags2       |              Flags.              |             Flags1 bit 0 is on.              |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   |       Flags3       |              Flags.              |             Flags2 bit 0 is on.              |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   | Type of tile (LSB) |             Tile ID              |             Flags1 bit 0 is on.              |
|   1   | Type of tile (MSB) |             		                |             Flags1 bit 5 is on.              |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   |    FrameX (LSB)    |   Involves tileframeimportant.   |      tileframeimportant[tile ID] is on.      |
|   1   |    FrameX (MSB)    |   							    |      									       |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   |    FrameY (LSB)    |   Involves tileframeimportant.   |      tileframeimportant[tile ID] is on.      |
|   1   |    FrameY (MSB)    |   							    |      									       |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   | Paint of the tile  | Unimportant data, no ID list yet |             Flags3 bit 3 is on.              |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   |    Type of wall    | 			   Wall ID              |             Flags1 bit 2 is on.              |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   | Paint of the wall  | Unimportant data, no ID list yet |             Flags3 bit 4 is on.              |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   |  Volume of liquid  | How much liquid is in this tile  |  Either Flags1 bit 3 OR Flags1 bit 4 are on. |
|		|					 |	(0x00 is empty, 0xFF is full)   |                                              |
+-------+--------------------+----------------------------------+----------------------------------------------+
|   1   |     RLE (LSB)      |   How many times this tile is    |             Flags1 bit 6 is on.              |
|	1	|	  RLE (MSB) 	 |   duplicated after this tile.    |             Flags1 bit 7 is on.              |
+-------+--------------------+----------------------------------+----------------------------------------------+

Flags1 - Contains the most important tile data (type of tile, liquid, run-length encoding).
		+--------+
		|76543210|
		|10011011|
		+--------+
	Bit 0 - Flags2 exists.
	Bit 1 - Tile isn't air.
	Bit 2 - There's a wall behind this tile.
	Bit 3 - Type of liquid.
	Bit 4 - Type of liquid, continued.
	Bit 5 - Tile is stored on two bytes (MSB + LSB) instead of 1 (LSB)
	Bit 6 - Run-length encoding is on (up to 255 tiles)
	Bit 7 - Longer run-length encoding is on (255 to 65535 tiles)

Flags2 - Contains slope and wire data.
		+--------+
		|76543210|
		|11001010|
		+--------+
	Bit 0 - Flags3 exists.
	Bit 1 - A red wire exists here.
	Bit 2 - A blue wire exists here.
	Bit 3 - A green wire exists here.
	Bit 4 - This is a half-tile or slope.
	Bit 5 - Ditto.
	Bit 6 - Ditto.
	Bit 7 - Unused.

Flags3 - Contains actuator and paint data.
		+--------+
		|76543210|
		|00011000|
		+--------+
	Bit 0 - Unused.
	Bit 1 - There's an actuator here.
	Bit 2 - This tile is actuated.
	Bit 3 - This tile is painted.
	Bit 4 - The wall behind this tile is painted.
	Bit 5 - Unused.
	Bit 6 - Unused.
	Bit 7 - Unused.
	If Flags2 doesn't exist, this flag doesn't exist either.

Liquid data as stored in Flags1:
76543210
___00___ - No liquid
___01___ - Water
___10___ - Lava
___11___ - Honey

Slope data as stored in Flags2:
76543210
_000____ - Tile is square
_001____ - Half-tile
_010____ - Slope with top-right corner missing
_011____ - Slope with top-left corner missing
_100____ - Slope with bottom-right corner missing
_101____ - Slope with bottom-left corner missing
_110____ - Unused
_111____ - Unused
"""

print(
"""
$$$$$$$$\ $$$$$$$\                      $$\  $$$$$$\            
\__$$  __|$$  __$$\                     \__|$$  __$$\           
   $$ |   $$ |  $$ |$$\   $$\  $$$$$$\  $$\ $$ /  \__|$$\   $$\ 
   $$ |   $$$$$$$  |$$ |  $$ |$$  __$$\ $$ |$$$$\     $$ |  $$ |
   $$ |   $$  ____/ $$ |  $$ |$$ |  \__|$$ |$$  _|    $$ |  $$ |
   $$ |   $$ |      $$ |  $$ |$$ |      $$ |$$ |      $$ |  $$ |
   $$ |   $$ |      \$$$$$$  |$$ |      $$ |$$ |      \$$$$$$$ |
   \__|   \__|       \______/ \__|      \__|\__|       \____$$ |
                                                      $$\   $$ |
                                                      \$$$$$$  |
                                                       \______/ 
                                                                     
   "Because fuck the Clentaminator"
   made by memethyl
""")

print("""
+=================================================================================+
|  Tiles Purified   Time Elapsed   Flags1    Flags2    Flags3   Tile ID   Wall ID |
""", end="")

# wall IDs are here just in case
corruptedTileIDs = {"23": 2, "25": 1, "32": 69, "112": 53, "163": 161, "398": 397, "400": 396}
#corruptedWallIDs = {"3": 1, "69": 63, "188": 1, "189": 1, "190": 1, "191": 1, "217": 216, "220": 187}

crimsonedTileIDs = {"199": 2, "200": 161, "203": 1, "234": 53, "352": 69, "399": 397, "401": 396}
#crimsonedWallIDs = {"81": 63, "83": 1, "192": 1, "193": 1, "194": 1, "195": 1, "218": 216, "221": 187}

hallowedTileIDs = {"109": 2, "116": 53, "117": 1, "164": 161, "402": 397, "403": 396}
#hallowedWallIDs = {"28": 1, "70": 63, "200": 1, "201": 1, "202": 1, "203": 1, "219": 216, "222": 187}

tiles_purified = 0
purifyHallow = args.purifyHallow
now = time.time()

while file.tell() < section_pointers[2]:
	flags1 = reader.bool(1)[0]
	flags2 = 0b00000000
	flags3 = 0b00000000
	tileID = 0
	wallID = 0

	# read flags
	if flags1 & 0b00000001 >= 1:
		flags2 = reader.bool(1)[0]
		if flags2 & 0b00000001 >= 1:
			flags3 = reader.bool(1)[0]

	# replaces corrupted/crimsoned tiles with their pure counterparts
	if flags1 & 0b00000010 >= 1:
		if flags1 & 0b00100000 >= 1:
			# two bytes
			tileID = reader.short(1)[0]
			try:
				if corruptedTileIDs[str(tileID)]:
					# corruption
					file.seek(-2, 1)
					file.write(struct.pack('<H', corruptedTileIDs[str(tileID)]))
					tiles_purified += 1
			except KeyError:
				try:
					if crimsonedTileIDs[str(tileID)]:
						# crimson
						file.seek(-2, 1)
						file.write(struct.pack('<H', crimsonedTileIDs[str(tileID)]))
						tiles_purified += 1
				except KeyError:
					if purifyHallow:
						try:
							if hallowedTileIDs[str(tileID)]:
								# hallow
								file.seek(-2, 1)
								file.write(struct.pack('<H', hallowedTileIDs[str(tileID)]))
								tiles_purified += 1
						except KeyError:
							# tile's clean
							pass
					else:
						# tile's clean
						pass
		else:
			# one byte
			tileID = reader.byte(1)[0]
			try:
				if corruptedTileIDs[str(tileID)]:
					# corruption
					file.seek(-1, 1)
					file.write(struct.pack('B', corruptedTileIDs[str(tileID)]))
					tiles_purified += 1
			except KeyError:
				try:
					if crimsonedTileIDs[str(tileID)]:
						# crimson
						file.seek(-1, 1)
						file.write(struct.pack('B', crimsonedTileIDs[str(tileID)]))
						tiles_purified += 1
				except KeyError:
					if purifyHallow:
						try:
							if hallowedTileIDs[str(tileID)]:
								# hallow
								file.seek(-1, 1)
								file.write(struct.pack('B', hallowedTileIDs[str(tileID)]))
								tiles_purified += 1
						except KeyError:
							# tile's clean
							pass
					else:
						# tile's clean
						pass
	else:
		# air has no tileID, so set this to 0 i guess
		# note: air has no tile ID, 0 is the ID for dirt
		# but it doesn't matter because dirt is pure anyway
		tileID = 0

	elapsed = time.time()-now
	hours = floor(elapsed/3600)
	minutes = floor(elapsed/60)
	seconds = floor(elapsed - (3600*hours) - (60*minutes))
	elapsed = '{0}:{1}:{2}'.format(format(hours,'02d'), format(minutes,'02d'), format(seconds,'02d'))
	print("|    {0}       {1}    {2}  {3}  {4}    {5}       {6}   |\r".format(
		  '{0}{1},{2}{3}{4},{5}{6}{7}'.format(*format(tiles_purified,'08d')), elapsed, format(flags1, '08b'), 
		  format(flags2, '08b'), format(flags3, '08b'), format(tileID, '03d'), format(wallID, '03d')),
	  	  end="")

	# tileframeimportant
	if int(tileframeimportant[tileID]) == 1:
		file.read(4)

	# tile paint
	if flags3 & 0b00001000 >= 1:
		file.read(1)

	# wall ID
	# corruption/crimson doesn't spread from wall to tile, so we don't need to replace these
	if flags1 & 0b00000100 >= 1:
		wallID = reader.byte(1)
	
	# wall paint
	if flags3 & 0b00010000 >= 1:
		file.read(1)
	
	# liquid
	if flags1 & 0b00001000 >= 1 or flags1 & 0b00010000 >= 1:
		file.read(1)

	# run-length encoding
	if flags1 & 0b10000000 >= 1:
		file.read(2)
	elif flags1 & 0b01000000 >= 1:
		file.read(1)
	else:
		pass

# this code might as well be changing the extension to wld
file.close()
copyfile(dst, src[0:-4]+'_purified.wld')
remove(dst)
print("\n\nWorld purified; data saved to {0}".format(src[0:-4]+'_purified.wld'))
