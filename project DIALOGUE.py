# -*- coding: utf-8 -*-
# author: Superkebabbie
# version: 1.2 (wrapping up)

displayName = "Project DIALOGUE"

import sys, os
support_dir = os.path.realpath(os.path.abspath(os.path.join('stock-filters','projectDialogue')))
if os.path.exists(support_dir):
    sys.path.insert(0, support_dir)#enforces loading of support code rather than default ETree installations
else:
    raise Exception("Could not find support files! Make sure the projectDIALOGUE folder is in the 'stock-filters' folder of MCEdit!")
    
from math import floor
import random
from pymclevel import TAG_List, TAG_Byte, TAG_Int, TAG_Compound, TAG_Short, TAG_Double, TAG_String, TAG_Float, TAG_Long
from numpy import zeros
import mcplatform, albow
import ElementTree as xTree
import re

class Style:    
    def __init__(self,str):
        #l=bold,o=italic,n=underline,m=strikethrough,k=obfuscated
        self.bold = True          if 'l' in str else False
        self.italic = True        if 'o' in str else False
        self.underlined = True    if 'n' in str else False
        self.strikethrough = True if 'm' in str else False
        self.obfuscated = True    if 'k' in str else False
    
    def toTellrawProperties(self):
        return "%s%s%s%s%s"%(',"bold":%s'%str(self.bold).lower(),
                             ',"italic":%s'%str(self.italic).lower(),
                             ',"underlined":%s'%str(self.underlined).lower(),
                             ',"strikethrough":%s'%str(self.strikethrough).lower(),
                             ',"obfuscated":%s'%str(self.obfuscated).lower())
    
    def copy(self):
        return Style('%s%s%s%s%s'%('l' if self.bold else '',
                                   'o' if self.italic else '',
                                   'n' if self.underlined else '',
                                   'm' if self.strikethrough else '',
                                   'k' if self.obfuscated else ''))

#---------------- ELEMENT HANDLERS ----------------#

def handleText(element,vars):
    #leaf function
    vars = readAttributes(element,vars,['delay','col','style','name','namecol','namestyle'])
    vars = doConvergence(vars)
    lines = [s for s in [l.lstrip('\t ') for l in element.text.split('\n')] if s != '']#string formatting: cut newlines and tabs and remove empty lines
    for l in lines:
        (x,y,z) = getNextWorkCoord()
        try:
            makeCommandBlock(x,y,z,getCommandBlockOrientation(),toMessage(l,vars),'chain',False,False,False)
        except UnknownFormattingCodeError as e:
            albow.dialogs.alert("Warning: %s in 't' at line %d"%(str(e),element.sourceline))
        vars['tick'] += vars['delay']
    goDeeper(element,vars,[])#checks if leaf does not have children
    vars = makeEnd(vars)
    return vars
        
def handleCommand(element,vars):
    #leaf function
    vars = readAttributes(element,vars,['delay'])
    vars = doConvergence(vars)
    lines = [s for s in [l.lstrip('\t ') for l in element.text.split('\n')] if s != '']#string formatting: cut newlines and tabs and remove empty lines
    for l in lines:
        (x,y,z) = getNextWorkCoord()
        makeCommandBlock(x,y,z,getCommandBlockOrientation(),toCommand(vars['tick'],vars['seg'],l),'chain',False,False,False)
        vars['tick'] += vars['delay']
    goDeeper(element,vars,[])#checks if leaf does not have children
    vars = makeEnd(vars)
    return vars
    
def handlePause(element,vars):
    #leaf function
    vars = readAttributes(element,vars,[])#run to give users feedback if the use attibutes here (of which there are none supported here)
    vars = doConvergence(vars)
    vars['tick'] += int(element.text)
    goDeeper(element,vars,[])#checks if leaf does not have children
    vars = makeEnd(vars)
    return vars
    
def handleConcatText(element,vars):
    #leaf function, only to be used within a concat
    vars = readAttributes(element,vars,['col','style'])
    lines = [s for s in [l.lstrip('\t ') for l in element.text.split('\n')] if s != '']#string formatting: cut newlines and tabs and remove empty lines
    vars['name'] = '' #removes name compound from underlying text elements
    for l in lines:
        try:
            vars['compounds'].extend(constructCompounds(l,vars))
        except UnknownFormattingCodeError as e:
            albow.dialogs.alert("Warning: %s in 't' at line %d"%(str(e),element.sourceline))
    goDeeper(element,vars,[])#checks if leaf does not have children
    return vars
    
def handleConcat(element,vars):
    #semi-leaf, only accepts t
    #makes all t contained within a single line, allows for easy formatting
    global getHandleFunction
    vars = readAttributes(element,vars,['col','style','name','namecol','namestyle','sep'])
    vars = doConvergence(vars)
    getHandleFunction['t'] = handleConcatText #override handle function
    vars['compounds'] = []
    if vars['name'] != '': vars['compounds'].append(TextCompound('[%s] '%vars['name'],vars['namecol'],vars['namestyle']))
    vars = goDeeper(element,vars,['t'],upstream_vars=['maxSeg','ends','tick','compounds'])
    if 'sep' in vars:
        start = 1 if vars['name'] == '' else 2#no sep between name and first compound
        for idx in reversed(range(start,len(vars['compounds']))):
            vars['compounds'].insert(idx,TextCompound(vars['sep'],vars['textcol'],vars['style']))
    (x,y,z) = getNextWorkCoord()
    makeCommandBlock(x,y,z,getCommandBlockOrientation(),toCommand(vars['tick'],vars['seg'],'tellraw @a '+toTellraw(vars['compounds'])),'chain',False,False,False)
    getHandleFunction['t'] = handleText #reset handle function
    vars['tick'] += vars['delay']
    vars = makeEnd(vars)
    return vars
        
def handleOption(element,vars):
    #recursive function
    if vars['seg'] in vars['ends']:
        del vars['ends'][vars['seg']]
    vars = readAttributes(element,vars,['delay','opcol','opstyle','col','style','name','namecol','namestyle'],ignore=['t'])
    vars['maxSeg'] += 1 #this is the next segment to jump to
    tickMem = vars['tick']
    col, style = '',''
    if 'opcol' in element.attrib and element.attrib['opcol'].startswith('!'): #deal with local overrides for the text of the option
        col = element.attrib['opcol'].lstrip('!')
    else:
        col   = getOptionAttribute(vars['opcols'],vars['maxSeg']-vars['seg'],vars['textcol'])
    if 'opstyle' in element.attrib and element.attrib['opstyle'].startswith('!'):
        style = element.attrib['opstyle'].lstrip('!')
    else:
        style = getOptionAttribute(vars['opstyle'],vars['maxSeg']-vars['seg'],vars['style'])
    if 't' not in element.attrib:
        raise xTree.ParseError("Missing required attribute 't' in option at line %d"%element.sourceline)
    (x,y,z) = getNextWorkCoord()
    makeCommandBlock(x,y,z,getCommandBlockOrientation(),toOption(element.attrib['t'],col,style,vars),'chain',False,False,False)
    vars['trans'].append(toTransition(vars['seg'],vars['maxSeg']))
    vars['tick'] = 0
    segMem = vars['seg']
    vars['seg'] = vars['maxSeg']
    vars = goDeeper(element,vars)
    vars['tick'] = tickMem
    vars['seg'] = segMem
    return vars
    
def handleInstant(element,vars):
    #recursive function, everything within is executed at the same time
    vars = readAttributes(element,vars,['opcol','opstyle','col','style','name','namecol','namestyle'])
    vars['delay'] = 0
    vars = goDeeper(element,vars)
    return vars
    
def handleWrap(element,vars):
    #recursive function, but no upward passing
    vars = readAttributes(element,vars,['delay','opcol','opstyle','col','style','name','namecol','namestyle'])
    vars = goDeeper(element,vars)
    return vars
    
def handleDialogue(element,vars):
    #top-layer function
    global maxDiaNum
    vars['ends'] = {} #reinstance, because python does ref passing for dicts
    vars['trans'] = []
    vars = readAttributes(element,vars,['delay','opcol','opstyle','col','num','name','style','namecol','namestyle'])
    if vars['num'] == 0:
        vars['num'] = maxDiaNum+1
    maxDiaNum = max(vars['num'],maxDiaNum)
    newDialogue(vars['num'])
    print('Assigning number ' + str(vars['num']) + ' to dialogue \'' + vars['name'] + '\' at line ' + str(element.sourceline))
    vars = goDeeper(element,vars)
    for command in vars['trans']:#append the transition block
        (x,y,z) = getNextWorkCoord()
        makeCommandBlock(x,y,z,getCommandBlockOrientation(),command,'chain',False,False,False)
    (x,y,z) = getNextWorkCoord()
    makeCommandBlock(x,y,z,getCommandBlockOrientation(),'scoreboard players set @a[score_dSeg_min=1] dSeg 0','chain',False,False,False)
    (x,y,z) = getNextWorkCoord()
    makeCommandBlock(x,y,z,getCommandBlockOrientation(),toCommand(vars['tick'],vars['maxSeg'],'scoreboard players set @e[tag=tracker] dNum 0'),'chain',False,False,False)
    return vars   

def handleTree(element):
    #root function
    vars = {                #init all variables to default:
        'name'   : '',          #name of the speaker
        'namecol': 'white',     #colour of the name
        'namestyle': Style(''), #style of the name
        'num'    : 0,           #num of the dialogue
        'tick'   : 0,           #amount of ticks into the current segment
        'delay'  : 40,          #standard delay between two messages in ticks
        'seg'    : 0,           #segment number in the current dialogue
        'maxSeg' : 0,           #tracker of the highest segment number that has been used in the tree. New segments are made with number maxSeg+1
        'textcol' : 'white', #colour of the spoken text
        'opcols' : [None],      #colours of the options, a list that is looped
        'opstyle': [Style('')], #styles of the options, also looped list
        'style'  : Style(''),   #text style following MC formatting options, see Style class for more
        'ends'   : {},          #dict of tree leaves, used for convergence
        'trans'  : [],          #list of transitions (either interactive or through convergence), to be appended at the end of the dialogue
    }
    vars = readAttributes(element,vars,['delay','opcol','opstyle','col','style','namecol','namestyle'])
    vars['tick'] = 0 #reading a new delay in collection might have updated the tick, reset
    goDeeper(element,vars,accepted_tags=['dialogue'],upstream_vars=[])#top layer doesn't accept any upstream vars, so each dialogue starts with the same vars.
    
getHandleFunction = { #maps element tags to the handling function (needs to be defined after all the functions
    't'       : handleText,
    'dialogue': handleDialogue,
    'option'  : handleOption,
    'command' : handleCommand,
    'wrap'    : handleWrap,
    'pause'   : handlePause,
    'instant' : handleInstant,
    'concat'  : handleConcat,
}
    
# ------------ ATTRIBUTES ------------#

#update functions have as first argument the vars struct and second the value of the attribute
#and they return a new vars struct with the relevant vars adjusted.
    
def updateDelay(vars,delay):
    oldDelay = vars['delay']
    newDelay = int(delay)
    vars['delay'] = int(delay)
    vars['tick']  = max(0,vars['tick']-(oldDelay-newDelay)) #correct for difference
    return vars
    
def updateOpstyle(vars,opstyle):
    if not opstyle.startswith('!'):
        vars['opstyle'] = [Style(style) if style != 'style' else None for style in opstyle.split(',')]
    return vars
    
def updateOpcol(vars,opcol):
    if not opcol.startswith('!'):
        vars['opcols'] = [str(col) if col != 'col' else None for col in opcol.split(',')]
    return vars
    
def updateCol(vars,col):
    vars['textcol'] = col
    return vars
    
def updateStyle(vars,style):
    vars['style'] = Style(style)
    return vars
    
def updateNum(vars,num):
    global maxDiaNum
    vars['num'] = int(num)
    if vars['num'] > maxDiaNum: maxDiaNum = vars['num']
    return vars
    
def updateName(vars,name):
    vars['name'] = name
    return vars
    
def updateNamecol(vars,namecol):
    vars['namecol'] = namecol
    return vars
    
def updateNamestyle(vars,namestyle):
    vars['namestyle'] = namestyle
    return vars
    
def readSep(vars,sep):
    #reads a separator string, used (only) in concat
    vars['sep'] = sep
    return vars
    
getUpdateAttributeFunction = { #maps attribute names to handling functions
    'delay' : updateDelay,
    'opcol' : updateOpcol,
    'opstyle':updateOpstyle,
    'num'   : updateNum,
    'col'   : updateCol,
    'name'  : updateName,
    'style' : updateStyle,
    'namecol':updateNamecol,
    'namestyle':updateNamestyle,
    'sep'   : readSep,
}
    
# -------------- XML HELPERS -------------#    

def goDeeper(element,vars,accepted_tags=['t','option','command','pause','instant','wrap','concat'],upstream_vars=['maxSeg','seg','ends','tick']):
    #accepted_tags: tags of elements that are allowed to occur at this layer. Defaults to what is accepted in the recursive area of a dialogue tree.
    #upstream_vars: variables that are passed back upstream, while other only go down
    for e in element:
        if e.tag in accepted_tags:
            varsUp = getHandleFunction[e.tag](e,vars.copy())
            for v in upstream_vars:
                vars[v] = varsUp[v]
        else:
            raise xTree.ParseError("Invalid element of type '%s' in '%s' at line %d.\n\n(%s)"%
                    (e.tag,
                    element.tag,
                    e.sourceline,
                    'must be one of: %s'%(str(', '.join(accepted_tags))) if accepted_tags != [] else 'no elements are accepted here'))
    return vars

def readAttributes(element,vars,acceptedAtts,ignore=[]):
    #for all attributes in the element, call the relevant function to update them
    #acceptedAtts: list of attributes that are allowed for a given element
    #ignore: a list of attributes that may exist in an element but who's value is ignored
    #attributes that do not occur in either list but are in the element will produce a warning.
    ignored = []
    for v in element.attrib.keys():
        if v in acceptedAtts:
            vars = getUpdateAttributeFunction[v](vars,element.attrib[v])
        elif v not in ignore:
            ignored.append(v)
    if ignored != []:
        albow.dialogs.alert("Warning: ignored attribute%s %s in %s at line %d.\n\n(Must be one of %s)"%
                ('s' if len(ignored) > 1 else '',
                ', '.join(["'"+s+"'" for s in ignored]),
                element.tag,
                element.sourceline,
                ', '.join(acceptedAtts)))
    return vars
    
def getOptionAttribute(attributes,opNum,default):
    #for a list such as opcols and opstyle, get the relevant item or the default (textcol/textStyle) if it is None
    #opNum should start at 0
    col = attributes[(opNum-1)%len(attributes)]
    if col == None:
        return default
    else:
        return col
    
def doConvergence(vars):
    #for all ends in the ends list, make a command block that syncs that end up with the current segment, then empty the list
    #any leaf node is both a potential end and a point where convergence is necessary
    converged = False
    for endSeg in vars['ends'].keys():
        if vars['seg'] < endSeg:
            #there are open ends
            converged = True
            endTick = vars['ends'][endSeg]
            vars['trans'].append('scoreboard players set @e[tag=tracker,score_dTim_min=%d,score_dTim=%d,score_dOldSeg_min=%d,score_dOldSeg=%d] dSeg %d'%
                    (endTick,
                     endTick,
                     endSeg,
                     endSeg,
                     vars['maxSeg']+1))
            del vars['ends'][endSeg]
    if converged:
        vars['maxSeg'] += 1
        vars['seg'] = vars['maxSeg']
        vars['tick'] = 0
    return vars
    
def makeEnd(vars):
    #make a new end for this segment
    vars['ends'][vars['seg']] = vars['tick']
    return vars
            
def getTree(filename):
    root = xTree.parse(filename).getroot()
    return root
    
# ------------- COMMANDS -------------#

def toCommand(time,seg,command):
    return 'execute @e[tag=tracker,score_dTim_min=%d,score_dTim=%d,score_dSeg_min=%d,score_dSeg=%d] ~ ~ ~ %s'%(time,time,seg,seg,command)

def toTransition(segFrom,segTo):
    return 'scoreboard players operation @e[tag=tracker,score_dOldSeg_min=%d,score_dOldSeg=%d] dSeg = @a[score_dSeg_min=%d,score_dSeg=%d] dSeg'%(segFrom,segFrom,segTo,segTo)

def toMessage(text,vars):
    #construct the basic (non-interactable) tellraw message for a command block
    compounds = constructCompounds(text,vars)
    return toCommand(vars['tick'],vars['seg'],'tellraw @a ' + toTellraw(compounds))
    
def constructCompounds(text,vars):
    compounds = []
    if vars['name'] != '': compounds.append(TextCompound('[%s] '%vars['name'],vars['namecol'],vars['namestyle']))
    splitOnFormat = [s for s in re.split(u'(\xa7.)',text) if s != '']
    workcol = vars['textcol']
    workstyle = vars['style'].copy()#local version of col and style that only apply to this text
    colmem = workcol
    stymem = workstyle.copy()
    for fs in splitOnFormat:
        if fs.startswith(u'\xa7'):
            #this is a formatting character, adjust vars
            workcol,workstyle = handleFormattingCode(fs[1],workcol,workstyle,colmem,stymem)
        else:
            splitOnSelectors = [x for x in re.split('(@.\[.+?\]|@.)',fs) if x != '']
            for ss in splitOnSelectors:
                if ss.startswith('@'):
                    #this is a selector
                    compounds.append(SelectorCompound(ss,workcol,workstyle))
                else:
                    compounds.append(TextCompound(ss,workcol,workstyle))
    return compounds
    
def constructOptionCompounds(text,workcol,style,clickevent):
    splitOnFormat = [s for s in re.split(u'(\xa7.)',text) if s != '']
    workstyle = style.copy()#local version of col and style that only apply to this text
    colmem = workcol
    stymem = workstyle.copy()
    compounds = [TextCompound('[',colmem,stymem,clickevent)]
    for fs in splitOnFormat:
        if fs.startswith(u'\xa7'):
            #this is a formatting character, adjust vars
            workcol,workstyle = handleFormattingCode(fs[1],workcol,workstyle,colmem,stymem)
        else:
            splitOnSelectors = [x for x in re.split('(@.\[.+?\]|@.)',fs) if x != '']
            for ss in splitOnSelectors:
                if ss.startswith('@'):
                    #this is a selector
                    compounds.append(TextCompound(ss,workcol,workstyle,extra=clickevent))
                    #TODO (LATER VERSION): If Mojang fixes issue MC-55493, use line below to enable selectors in option (that have a working clickEvent).
                    #compounds.append(SelectorCompound(ss,workcol,workstyle,extra=clickevent))
                else:
                    compounds.append(TextCompound(ss,workcol,workstyle,extra=clickevent))
    compounds.append(TextCompound(']',colmem,stymem,clickevent))
    return compounds
        
class UnknownFormattingCodeError(Exception):
    pass
        
def handleFormattingCode(mode,workcol,workstyle,defcol,defstyle):
    #take a formatting code (§x) and update vars accordingly
    if   mode == '0': workcol = 'black'
    elif mode == '1': workcol = 'dark_blue'
    elif mode == '2': workcol = 'dark_green'
    elif mode == '3': workcol = 'dark_aqua'
    elif mode == '4': workcol = 'dark_red'
    elif mode == '5': workcol = 'dark_purple'
    elif mode == '6': workcol = 'gold'
    elif mode == '7': workcol = 'gray'
    elif mode == '8': workcol = 'dark_gray'
    elif mode == '9': workcol = 'blue'
    elif mode == 'a': workcol = 'green'
    elif mode == 'b': workcol = 'aqua'
    elif mode == 'c': workcol = 'red'
    elif mode == 'd': workcol = 'light_purple'
    elif mode == 'e': workcol = 'yellow'
    elif mode == 'f': workcol = 'white'
    elif mode == 'k': workstyle.obfuscated = True
    elif mode == 'l': workstyle.bold = True
    elif mode == 'm': workstyle.strikethrough = True
    elif mode == 'n': workstyle.underlined = True
    elif mode == 'o': workstyle.italic = True
    elif mode == 'r':
        workcol = defcol
        workstyle = defstyle.copy()
    else: raise UnknownFormattingCodeError("encountered unknown formatting code %s"%mode)
    return workcol,workstyle
        
             
class TextCompound():
    #JSON compound of text
    def __init__(self,text,colour,style,extra=''):
        self.text = text
        self.colour = colour
        self.style = style.copy()
        self.extra = extra
        
    def encode(self):
        return '{"text":"%s"%s%s%s}'%(
            self.text,
            ',"color":"%s"'%(self.colour),
            self.style.toTellrawProperties(),
            self.extra)
            
class SelectorCompound():
    #JSON compound that consists of a selector
    def __init__(self,selector,colour,style,extra=''):
        self.selector = selector.encode('utf-8')
        self.colour = colour
        self.style = style.copy()
        self.extra = extra
        
    def encode(self):
        return '{"selector":"%s"%s%s%s}'%(
            self.selector,
            ',"color":"%s"'%(self.colour),
            self.style.toTellrawProperties(),
            self.extra)
             
def toTellraw(compounds):
    #take a list of JSON compounds and produce the entire tellraw JSON argument
    return '[%s]'%','.join([c.encode() for c in compounds])        
    
def toOption(text,colour,style,vars):
    #This command needs the dialogue number and old segment to make sure the options are only clickable at one moment
    compounds = constructOptionCompounds(text,colour,style,',"clickEvent":{"action":"run_command","value":"/trigger dSeg set %d"}'%vars['maxSeg'])
    return toCommand(vars['tick'],vars['seg'],'tellraw @a ' + toTellraw(compounds))

#--------------- WORLD ---------------#

directionNum = {
'north': 2,
'south': 3,
'west' : 4,
'east' : 5,
'up'   : 1,
'down' : 0
}

def getNextWorkCoord():
    #update workX, -Y and -Z to point to the next coordinate according to the build plan
    global minX,minY,minZ,workX,workY,workZ,maxX,maxY,maxZ,xDirection,yDirection
    if (not compactMode) and (workZ-(minZ-1))%3 == 0:
        #not compact mode, every 3 slices skip one
        if workZ == maxZ: albow.dialogs.alert('Not enough space provided! Exceeding limits in the positive Z direction (south).')
        workZ += 1
        return (workX,workY,workZ)
    if (xDirection == 1 and workX == maxX) or (xDirection == -1 and workX == minX):
        xDirection *= -1#flip the direction
        if (yDirection == 1 and workY == maxY) or (yDirection == -1 and workY == minY):
            #filled a whole slice, go to the next one (on z axis)
            yDirection *= -1
            if workZ == maxZ: albow.dialogs.alert('Not enough space provided! Exceeding limits in the positive Z direction (south).')
            workZ += 1
        else:
            workY += yDirection
    else:
        workX += xDirection
    return (workX,workY,workZ)
    
def getCommandBlockOrientation():
    if (not compactMode) and (workZ-(minZ-1))%3 == 0:
        return 'south'
    if (xDirection == 1 and workX == maxX) or (xDirection == -1 and workX == minX):
        if (yDirection == 1 and workY == maxY) or (yDirection == -1 and workY == minY):
            #go to new slice, point to positive Z
                return 'south'
        else:
            if yDirection == 1:
                return 'up' 
            else: 
                return 'down'
    else:
        if xDirection == 1: 
            return 'east' 
        else: 
            return 'west'
            
def newDialogue(diaNum):
    #Starts a new chain of command blocks, used at a new dialogue
    global minX,minZ,workX,workY,workZ,xDirection,yDirection,compactMode
    if not compactMode:
        workX = minX
        workY = minY
        if workZ == maxZ-1 or workZ == maxZ: albow.dialogs.alert('Not enough space provided! Exceeding limits in the positive Z direction (south).')
        workZ += 2#leave a gap of 1 between the chains
        xDirection = 1
        yDirection = 1
        minZ = workZ#Update minZ to compute where the maintenance gaps in non-compact mode should go
    else:
        getNextWorkCoord()
    makeCommandBlock(workX,workY,workZ,getCommandBlockOrientation(),"/execute @e[tag=tracker,score_dNum_min=%d,score_dNum=%d] ~ ~ ~ /particle cloud ~ ~1 ~ 0 1 0 0.1"%(diaNum,diaNum),'repeating',False,False,False)
    getNextWorkCoord()
    makeCommandBlock(workX,workY,workZ,getCommandBlockOrientation(),'','repeating',False,True,False)

def inChunk(x,y,z):
    #return the chunk coordinates in which the coordinates belong
    return (int(floor(x/16)),int(floor(y/16)),int(floor(z/16)))
    
def ranUUID():
    #generate random numbers within the UUID range, use to give unique UUID to things and prevent conflicts!
    return random.randrange(-9999999999999999,9999999999999999)

def makeCommandBlock(x,y,z,facing,command,type,needsRedstone,conditional,trackOutput):
    #x y z are the coordinates where the block is placed
    #facing = {'north','south','west','east','up','down'} is direction of the block
    #command (string) is the command in the command block
    #type = {'normal','repeating','chain'}
    #needsRedstone (boolean) is whether the command block needs a redstone signal
    #conditional (boolean) is whether the command block is in conditional mode
    (cx, _, cz) = inChunk(x,y,z)
    chunk = lvl.getChunk(cx,cz)
    if type == 'normal':
        lvl.setBlockAt(x,y,z,137)
    elif type == 'repeating':
        lvl.setBlockAt(x,y,z,210)
        #add a TileTick to get the cblock running, else it will not automatically start
        tt = TAG_Compound()
        tt['i'] = TAG_String('minecraft:repeating_command_block')
        tt['p'] = TAG_Int(0)
        tt['t'] = TAG_Int(1)
        tt['x'] = TAG_Int(x)
        tt['y'] = TAG_Int(y)
        tt['z'] = TAG_Int(z)
        chunk.TileTicks.append(tt)
    elif type == 'chain':
        lvl.setBlockAt(x,y,z,211) 
    lvl.setBlockDataAt(x,y,z,directionNum[facing]+8*conditional)#see bytes http://minecraft.gamepedia.com/Command_Block
    tile_ent = TAG_Compound()
    tile_ent['powered'] = TAG_Byte(0)
    tile_ent['auto'] = TAG_Byte(not needsRedstone)
    tile_ent['TrackOutput'] = TAG_Byte(trackOutput)
    tile_ent['SuccessCount'] = TAG_Int(0)
    tile_ent['id'] = TAG_String(command_block_id)
    tile_ent['x'] = TAG_Int(x)
    tile_ent['y'] = TAG_Int(y)
    tile_ent['z'] = TAG_Int(z)
    tile_ent['Command'] = TAG_String(command)
    tile_ent['CustomName'] = TAG_String('@')
    chunk.TileEntities.append(tile_ent)
    chunk.dirty = True
    
def initWorld(x,y,z):
    #spawn the tracker, clock and all other necessities that each world needs somewhere!
    (cx, _, cz) = inChunk(x,y,z)
    chunk = lvl.getChunk(cx,cz)
    #INIT SCOREBOARD
    #CANT ACCESS SCOREBOARD, need c-block workaround!
    #Creates a series of command blocks that make the objectives and then self-destructs
    makeCommandBlock(x,y,z+3,'east','scoreboard objectives add dTim dummy Dialogue Ticks', 'repeating', False, False, False)
    makeCommandBlock(x+1,y,z+3,'east','scoreboard objectives add dNum dummy Dialogue Number', 'chain', False, False, False)
    makeCommandBlock(x+2,y,z+3,'up','scoreboard objectives add dSeg trigger Dialogue Interactive Segment', 'chain', False, False, False)
    makeCommandBlock(x+2,y+1,z+3,'west','scoreboard objectives add dOldNum dummy Last Dialogue Number', 'chain', False, False, False)
    makeCommandBlock(x+1,y+1,z+3,'west','scoreboard objectives add dOldSeg dummy Last Dialogue Segment', 'chain', False, False, False)
    makeCommandBlock(x,y+1,z+3,'up','gamerule commandBlockOutput false', 'chain', False, False, False)
    makeCommandBlock(x,y+2,z+3,'east','gamerule sendCommandFeedback false','chain',False,False,False)
    makeCommandBlock(x+1,y+2,z+3,'east','summon minecraft:ender_crystal ~-1 ~-1.5 ~-2 {CustomName:"Tracker",CustomNameVisible:1b,ShowBottom:0b,Invulnerable:1b,Tags:["tracker"]}','chain',False,False,False)
    makeCommandBlock(x+2,y+2,z+3,'up','fill ~ ~ ~ ~-2 ~-2 ~ air','chain',False,False,False)#<--self-destruct
    #SPAWN CLOCK
    makeCommandBlock(x,y,z+1,'up','scoreboard players add @e[tag=tracker] dTim 1','repeating',False,False,False)
    #SPAWN SCORE-UPDATE DETECTOR (SUD)
    makeCommandBlock(x,y,z,'east','scoreboard players operation @e[tag=tracker] dOldNum -= @e[tag=tracker] dNum','repeating',False,False,False)
    makeCommandBlock(x+1,y,z,'south','execute @e[tag=tracker,score_dOldNum_min=-999999999,score_dOldNum=-1] ~ ~ ~ scoreboard players set @e[tag=tracker] dTim -1','chain',False,False,False)
    makeCommandBlock(x+1,y,z+1,'south','execute @e[tag=tracker,score_dOldNum_min=1,score_dOldNum=999999999] ~ ~ ~ scoreboard players set @e[tag=tracker] dTim -1','chain',False,False,False)
    makeCommandBlock(x+1,y,z+2,'up','execute @e[tag=tracker,score_dOldNum_min=-999999999,score_dOldNum=-1] ~ ~ ~ scoreboard players set @e[tag=tracker] dSeg 0','chain',False,False,False)#reset dSeg for tracker
    makeCommandBlock(x+1,y+1,z+2,'north','execute @e[tag=tracker,score_dOldNum_min=1,score_dOldNum=999999999] ~ ~ ~ scoreboard players set @e[tag=tracker] dSeg 0','chain',False,False,False)
    makeCommandBlock(x+1,y+1,z+1,'north','execute @e[tag=tracker,score_dOldNum_min=1,score_dOldNum=999999999] ~ ~ ~ scoreboard players set @a dSeg 0','chain',False,False,False)#reset dSeg for players
    makeCommandBlock(x+1,y+1,z,'west','execute @e[tag=tracker,score_dOldNum_min=1,score_dOldNum=999999999] ~ ~ ~ scoreboard players set @a dSeg 0','chain',False,False,False)
    makeCommandBlock(x,y+1,z,'up','scoreboard players operation @e[tag=tracker] dOldNum = @e[tag=tracker] dNum','chain',False,False,False)
    makeCommandBlock(x,y+2,z,'east','scoreboard players operation @e[tag=tracker] dOldSeg -= @e[tag=tracker] dSeg','chain',False,False,False)
    makeCommandBlock(x+1,y+2,z,'south','execute @e[tag=tracker,score_dOldSeg_min=-999999999,score_dOldSeg=-1] ~ ~ ~ scoreboard players set @e[tag=tracker] dTim -1','chain',False,False,False)
    makeCommandBlock(x+1,y+2,z+1,'south','execute @e[tag=tracker,score_dOldSeg_min=1,score_dOldSeg=999999999] ~ ~ ~ scoreboard players set @e[tag=tracker] dTim -1','chain',False,False,False)
    makeCommandBlock(x+1,y+2,z+2,'up','scoreboard players operation @e[tag=tracker] dOldSeg = @e[tag=tracker] dSeg','chain',False,False,False)
    #TRIGGER OPERATOR
    makeCommandBlock(x,y,z+2,'up','scoreboard players enable @a dSeg','repeating',False,False,False)
    chunk.dirty = True

#------------- RUN ---------------#    
inputs = (
("Generate base (do once per world!)", False),
("Compact mode",True),
("Old minecraft world (if world is pre 1.11)",False),
)

def initGlobals(level,box,options):
    #Initalize all the global variables. MCEdit compiles the filter once at opening the 'filter' option, so a standard initilization will only run once!
    global minX,minY,minZ,workX,workY,workZ,maxX,maxY,maxZ,xDirection,yDirection,lvl,compactMode,maxDiaNum,command_block_id,ender_crystal_id
    compactMode = options["Compact mode"]
    command_block_id = "command_block"
    ender_crystal_id = "ender_crystal"
    if options["Old minecraft world (if world is pre 1.11)"]:
        command_block_id = u"Control"
        ender_crystal_id = u"EnderCrystal"
    minX = box.minx
    minY = box.miny
    minZ = box.minz
    workX = box.minx-1
    workY = box.miny
    workZ = box.minz-2 if not compactMode else box.minz
    maxX = box.maxx-1#box overshoots the actual coordinates in the box by 1
    maxY = box.maxy-1
    maxZ = box.maxz-1
    xDirection = 1
    yDirection = 1
    lvl = level
    maxDiaNum = 0

def perform(level, box, options):
    initGlobals(level,box,options)
    if options["Generate base (do once per world!)"]:
        initWorld(box.minx,box.miny,box.minz)
        global workZ, compactMode
        workZ = box.minz+2
        if compactMode:
            workZ += 2
    filename = mcplatform.askOpenFile(title="Select an XML file", schematics=False, suffixes=['xml'])
    if filename != None:
        root = getTree(filename)
        handleTree(root)