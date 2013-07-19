#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" 
  Reads a WAV file and convert it to BTC 1.0 bit stream format

  BTc Sound Compression Algortithm created by Roman Black
  http://www.romanblack.com/btc_alg.htm

"""

from __future__ import division

VERSION = '0.2'

CHUNK = 1024        # How many samples send to player
BYTES = 2           # N bytes arthimetic
MAX = 2**(BYTES*8 -1) -1
MIN = -(2**(BYTES*8 -1)) +1   

COLUMN = 8          # Prety print of values
PAD_FILL = 0        # Padding fill of 32 byte blocks


import sys
import time
import os.path
import array
from math import log, exp, floor, ceil
import wave
import audioop

# No stdlib modules
import pyaudio
from intelhex import IntelHex

import btc


class SoundsLib(object):
  """ Creates a sound lib of BTc codec sounds """

  def __init__(self, bitrate =22000, soft=24, codec='BTc1.0'):
    self.btc_codec  = codec     # Sound codec
    self.bitrate    = bitrate   # BitRate
    self.soft       = soft      # Desired softness constant
    self.sounds     = {}  # Dict 'filename' : {inputwave, resultwave, bitstream, info}
    self.snames     = []        # Sound names in insertion order

    self.r, self.c , self.info = btc.CalcRC(self.bitrate, soft) 
    self.info += "\tUsing %s\n" % codec
  
  def AddWAVSound(self, name):
    """ Adds a WAV file to the sound library """
    
    if not name in self.sounds:
      if not os.path.exists(name):
        raise IOError ("File %s don't exists" % name)

      sr, samples, info = ReadWAV(name)

      # Resample to lib bitrate
      if sr != self.bitrate:
        samples, state = audioop.ratecv(samples, BYTES, 1, sr, self.bitrate, None)

      name = name.split('.')[0]

      self.sounds[name] = {'inputwave': samples, 'resultwave': None, \
                                'bitstream': None, 'info': info}
      self.snames.append(name)

      return True
    else:
      return False


  def DelSound(self, name):
    del self.sounds[name]


  def Process(self):
    """ Process all sound with the desired codec and softness """
    for name in self.sounds.keys():
      if self.sounds[name]['resultwave'] is None:
        if self.btc_codec == 'BTc1.7':
          tmp, info = btc.PredictiveBTC1_7 ( self.sounds[name]['inputwave'], self.soft)
        else:
          tmp, info = btc.PredictiveBTC1_0 ( self.sounds[name]['inputwave'], self.soft)
        self.sounds[name]['bitstream'] = tmp
        self.sounds[name]['info'] += info


  def PlayOriginal (self, name):
    """ Plays Original sound if exists """
    if name in self.sounds:
      p = pyaudio.PyAudio() # Initiate audio system
      Play(p, self.bitrate, self.sounds[name]['inputwave'])
      p.terminate()
 
  
  def PlayProcesed (self, name):
    """ Plays Procesed sound if exists """
    if name in self.sounds:
      p = pyaudio.PyAudio() # Initiate audio system

      if self.sounds[name]['resultwave'] is None:
        if self.btc_codec == 'BTc1.7':
         self.sounds[name]['resultwave'] = \
             btc.DecodeBTC1_7 (self.sounds[name]['bitstream'] , self.soft)
        else:
         self.sounds[name]['resultwave'] = \
             btc.DecodeBTC1_0 (self.sounds[name]['bitstream'] , self.bitrate , \
             self.r, self.c)

      Play(p, self.bitrate, self.sounds[name]['resultwave'])
      p.terminate()

  
  def WriteToFile (self, filename, outputFormat, bias=0):
    """ Write to a file the Sound Lib using a output format function """

    f = None
    try:
      # Opening file
      if filename is None: # Try to open the file
        f = sys.stdout
      else:
        print(self.info)

        if outputFormat == 'btl' or outputFormat == 'raw':
          f = open(filename, 'wb')
        else:
          f = open(filename, 'w')

      # Writting
      if outputFormat == 'btl_ihex' or outputFormat == 'btl':
        ptr_addr = 0        # Were write Ptr to sound data end
        addr = 1024       # Were write sound data
        ih = IntelHex()
        
        for name in self.snames:
          if not f is sys.stdout:
            print(self.sounds[name]['info'])
          
          data = btc.BStoByteArray(self.sounds[name]['bitstream'])
          while len(data) % 32 != 0:     #Padding to fill 32 byte blocks
            data.append(PAD_FILL)

          BTLoutput(data, ih, addr, ptr_addr, bias)
          ptr_addr += 4
          addr += len(data)
        # Fills the header with 0s
        for n in xrange(ptr_addr, 1024):
          ih[n] = 0
        
        if outputFormat == 'btl' or outputFormat == 'btc': # Binary
          ih.tofile(f, 'bin')
        else:                     # IntelHex
          ih.tofile(f, 'hex')

      elif outputFormat == 'btc_ihex' or outputFormat == 'btc':
        addr = 0          # Were write sound data
        ih = IntelHex()
        
        for name in self.snames:
          if not f is sys.stdout:
            print(self.sounds[name]['info'])
          
          data = BStoByteArray(self.sounds[name]['bitstream'])
          while len(data) % 32 != 0:     #Padding to fill 32 byte blocks
            data.append(PAD_FILL)

          BTCoutput(data, ih, addr, bias)
          addr += len(data)
        
        if outputFormat == 'btc': # Binary
          ih.tofile(f, 'bin')
        else:                     # IntelHex
          ih.tofile(f, 'hex')
      
      elif outputFormat == 'c':
        for name in self.snames:
          if not f is sys.stdout:
            print(self.sounds[name]['info'])
          data = btc.BStoByteArray(self.sounds[name]['bitstream'])
          CArrayPrint(data, f, self.sounds[name]['info'], name);


    finally:
      if f != sys.stdout:
        f.close()


def ReadWAV (filename):
  """ Reads a wave file and return sample rate and mono audio data """

  # Make header info
  sys.stderr.write('Openining : ' + filename + '\n\n')
  wf = wave.open(filename, 'rb')
  
  info = "\tWAV file: " + filename + "\n"
  channels = wf.getnchannels()
  info += "\tOriginal Channels: " + str(channels)
  bits = wf.getsampwidth()
  info += "\tOriginal Bits: " + str(bits*8) + "\n"
  sr = wf.getframerate()
  total_samples = wf.getnframes()
  seconds = float(total_samples)/sr
  ms_seconds = (seconds - floor(seconds)) * 1000
  info += "\tOriginal Size: " + str(total_samples*wf.getsampwidth())
  info += " Bytes ( %d" % floor(seconds)
  info += ":%05.1f" % ms_seconds
  info += ") seconds \n"
  info += "\tSample Rate: " + str(sr) + "\n"


  samples = wf.readframes(total_samples)
  wf.close()
  if bits != BYTES: # It isn't 16 bits, convert to 16
    samples = audioop.lin2lin(samples, bits, BYTES)
    if bits == 1: # It's 8 bits
      samples = audioop.bias(samples, 2, -(2**(BITS*8-1)) ) # Correct from unsigned 8 bit

  if channels > 1:
    samples = audioop.tomono(samples, BYTES, 0.75, 0.25)

  # Normalize at 50%
  max = audioop.max(samples, BYTES)
  samples = audioop.mul(samples, BYTES, MAX*0.5/float(max))

  return sr, samples, info


def Play(audio, sr, samples):
  """Plays an audio data

  Keywords arguments:
  audio -- PyAduio Object
  sr -- Sample Rate
  samples -- Audio data in a string byte array (array.trostring())

  """
  stream = audio.open(format=audio.get_format_from_width(BYTES), \
    channels=1, \
    rate=sr, \
    output=True)

  data = samples[:CHUNK]
  i=0
  while i < len(samples):
    stream.write(data)
    i += CHUNK
    data = samples[i:min(i+CHUNK, len(samples))]

  time.sleep(0.5) # delay half second

  stream.stop_stream()
  stream.close()


def CArrayPrint (bytedata, f, head, name, ):
    """ Prints a Byte Array in a pretty C array format. 
    
    Keywords arguments:
    bytedata -- Stream of bytes to write
    f -- File were to write
    head -- Pretty comment text for the bytedata array
    name -- Name of the bytedata array

    """
    if head:
      f.write("/*\n" + head + "*/\n\n")
     
    data_str = map(lambda x: "0x%02X" % x, bytedata)
    f.write(name + "_len = " + str(len(data_str)) + "; /* Num. of Bytes */\n")

    # Print Bytedata
    f.write(name + "_data  = {\n")
    
    blq = data_str[:COLUMN]
    i = 0
    while i < len(data_str): 
      f.write(', '.join(blq) + ',\n')
      i += COLUMN
      if i%32 == 0:
        f.write('/*---------------- %8d ----------------*/\n' % i)

      blq = data_str[i:min(i+COLUMN, len(data_str))]

    f.write("}; \n")


def BTLoutput (bytedata, ih, addr, ptr_addr, bias=0):
  """ Write BTL Lib to a IHEX datastructure. 
  
  Keywords arguments:
  bytedata -- Stream of bytes to write
  ih -- IntelHex Object wre to write
  addr -- Address were store the bytedata
  ptr_addr -- Address were store the pointer to the end of the data
  biar -- Offset of addresses were write all
  
  """
  ptr = len(bytedata) + addr - 1024 # Relative to the end of header
  ptr = ptr//32   # Points to 32 bytes block, not real address
 
  ptr_addr += bias
  # Writes the pointer in the header
  ih[ptr_addr] = 0 # (ptr >> 24)
  ptr = ptr & 0x00FFFFFF
  
  ptr_addr +=1
  ih[ptr_addr] = ptr >> 16
  ptr = ptr & 0x0000FFFF
  
  ptr_addr +=1
  ih[ptr_addr] = ptr >> 8
  ptr = ptr & 0x000000FF
  
  ptr_addr +=1
  ih[ptr_addr] = ptr
  
  # Writes Data
  addr += bias
  for b in bytedata:
    ih[addr] = b
    addr +=1

def BTCoutput (bytedata, ih, addr, bias=0):
  """ Write BTC RAW to a IHEX datastructure. 
  
  Keywords arguments:
  bytedata -- Stream of bytes to write
  ih -- IntelHex Object wre to write
  addr -- Address were store the bytedata
  ptr_addr -- Address were store the pointer to the end of the data
  biar -- Offset of addresses were write all
  
  """ 
  # Writes Data
  addr += bias
  for b in bytedata:
    ih[addr] = b
    addr +=1


# MAIN !
if __name__ == '__main__':
  import argparse

  # Args parsing
  parser = argparse.ArgumentParser(description="Reads a WAV file, play it and" +\
      " play BTc1 conversion. Finally return C array BTC enconde data")

  parser.add_argument('infile', type=str, nargs='+', \
      metavar='file.wav', help='WAV file to be procesed')

  parser.add_argument('-o', '--output', type=str, \
      help="Output file. By default output to stdout")

  parser.add_argument('-c', choices=['BTc1.0', 'BTc1.7'], \
      default='BTc1.0', help='Desired Codec. Defaults: %(default)s')

  parser.add_argument('-s', '--soft', type=int, default=24 , \
      help='Softness constant. How many charge/discharge C in each time period.' + \
      ' Must be >2. Default: %(default)s ')

  parser.add_argument('-f', choices=['c', 'btl', 'btl_ihex', 'btc', 'btc_ihex'], \
      default='c', help='Output format. c -> C Array; ' + \
      'btl -> BotTalk Library; ' + \
      'btl_ihex -> BotTalk Library in IHEX format; '\
      'btc -> Headerless RAW binary; ' + \
      'btc_ihex -> Headerless RAW in IHEX format; '\
      ' Default: %(default)s')


  parser.add_argument('-b', '--bias', metavar='N', type=int, default=0 , \
      help='Bias or Padding of the output file. In RAW files' \
      " inserts N padding bytes before. In Intel HEX, it's the initial '\
      'address. Default: %(default)s ")

  parser.add_argument('-r', '--rate', metavar='BR', type=int, default=22000 , \
      help='Desired BitRate of procesed sound. Defaults: %(default)s bit/sec')

  parser.add_argument('-p', action='store_true', default=False, help='Plays procesed file')
  parser.add_argument('--playorig', action='store_true', default=False, help='Plays original file')
  parser.add_argument('--version', action='version',version="%(prog)s version "+ VERSION)

  args = parser.parse_args()
 
  # Check input values
  if args.soft < 2:
    print("Invalid value of softness constant. Must be > 2.")
    sys.exit(0)

  if args.bias < 0:
    print("Invalid value of bias/padding. Must be a positive value.")
    sys.exit(0)

  if args.rate < 1000:
    print("Invalid BitRate. Must be >= 1000.")
    sys.exit(0)

  for fname in args.infile:
    if not os.path.exists(fname):
      print("The input file %s don't exists." % fname)
      sys.exit(0)

  sl = SoundsLib(args.rate, args.soft, args.c)
  for f in args.infile:
    sl.AddWAVSound(f)

  if args.playorig:
    for k in sl.sounds.keys():
      print("Playing Original Sound: " + k)
      sl.PlayOriginal(k)

  # Process all sounds in the lib
  sl.Process()

  # Play procesed sounds
  if args.p:
    for k in sl.sounds.keys():
      print("Playing Procesed Sound: " + k)
      sl.PlayProcesed(k)

  # Write to output
  sl.WriteToFile(args.output, args.f)
  
