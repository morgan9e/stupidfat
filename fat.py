FILESYSTEM = "fs.img"
with open(FILESYSTEM, "rb") as f:
    fs = f.read()

class ByteArray:
    def __init__(self, data = b''):
        self.data = data
        self.read = 0

    def __getitem__(self, idx):
        return self.data[idx]

    def __repr__(self):
        return "0x" + "".join([hex(i)[2:].upper().zfill(2) for i in self.data])+ " (" + repr("".join([chr(i) for i in self.data])) + ")"

    def __int__(self):
        return int.from_bytes(self.data, byteorder='little', signed=False)

    def __str__(self):
        return self.cutws(str(repr("".join([chr(i) for i in self.data]))[1:-1]))

    def __add__(self, other):
        return ByteArray(self.data + other.data)

    def CRW(self):
        ret = self.data[self.read:self.read+2]
        self.read += 2
        return ByteArray(ret)

    def CRB(self):
        ret = self.data[self.read:self.read+1]
        self.read += 1
        return ByteArray(ret)

    def CR(self, size):
        ret = ByteArray(self.data[self.read:self.read+size])
        self.read += size
        return ret

    def RW(self, offset = None):
        return self.RR(2,offset)

    def RB(self, offset = None):
        return self.RR(1, offset)

    def RR(self, size, offset = None):
        if not offset:
            offset = self.read
        return ByteArray(self.data[offset:offset+size])

    def cutws(self, a):
        l = -1
        for n, i in reversed(list(enumerate(a))):
            if i != " ":
                l = n
                break
        return a[:l+1]

FS = ByteArray(fs)

FAT_DATA = {
    "BJI": FS.CR(0x3),
    "OEM": FS.CR(0x8)
}

BPB = FS.CR(13)
FAT_RESERVED_DATA = {
    "BytePerLogSect":  BPB.CRW(),
    "LogSectPerClus":  BPB.CRB(),
    "ReservedLogSect": BPB.CRW(),
    "NumFAT":          BPB.CRB(),
    "RootDE":          BPB.CRW(),
    "TotalLogSect":    BPB.CRW(),
    "MediaDesc":       BPB.CRB(),
    "LogSectPerFAT":   BPB.CRW(),
}

FAT_BYTE_PER_SECTOR       = int(FAT_RESERVED_DATA["BytePerLogSect"])
FAT_SECT_PER_CLUS         = int(FAT_RESERVED_DATA["LogSectPerClus"])
FAT_RESERVED_SECTOR_COUNT = int(FAT_RESERVED_DATA["ReservedLogSect"])
FAT_FAT_COUNT             = int(FAT_RESERVED_DATA["NumFAT"])
FAT_SECTOR_PER_FAT        = int(FAT_RESERVED_DATA["LogSectPerFAT"])
FAT_ROOT_DIRENT           = int(FAT_RESERVED_DATA["RootDE"])
FAT_SECT_COUNT            = int(FAT_RESERVED_DATA["TotalLogSect"])
FAT_BYTE_PER_CLUS         = FAT_BYTE_PER_SECTOR * FAT_SECT_PER_CLUS
FAT_RESERVED_SECTOR_SIZE  = FAT_BYTE_PER_SECTOR * FAT_RESERVED_SECTOR_COUNT

BPB = FS.CR(FAT_RESERVED_SECTOR_SIZE - 24)

FAT_RESERVED_DATA.update({
    # DOS 3.31
    "PSpT":            BPB.CRW(),
    "NH":              BPB.CRW(),
    "HiddenSect":      BPB.CR(4),
    "LTotalLogSect":   BPB.CR(4),
    # DOS 4.0
    "PDN":             BPB.CRB(),
    "FLG":             BPB.CRB(),   
    "EBS":             BPB.CRB(),
    "VolumeSN":        BPB.CR(4),
    "Label":           BPB.CR(11),
    "FSType":          BPB.CR(8)
})

print(f"""VOLUME \"{str(FAT_RESERVED_DATA["Label"])}\" TYPE {str(FAT_RESERVED_DATA["FSType"])}
- B/S: {FAT_BYTE_PER_SECTOR}       
- S/C: {FAT_SECT_PER_CLUS}         
- FAT: {FAT_FAT_COUNT}             
- S/F: {FAT_SECTOR_PER_FAT}        
- RDE: {FAT_ROOT_DIRENT}           
- TSC: {FAT_SECT_COUNT}            
- BPC: {FAT_BYTE_PER_CLUS}         
- RSC: {FAT_RESERVED_SECTOR_COUNT} 
""")

#print(FAT_FAT_COUNT, FAT_SECTOR_PER_FAT, FAT_BYTE_PER_SECTOR, \
#    FAT_SECT_PER_CLUS, FAT_SECTOR_PER_FAT)

FAT = FS.CR(FAT_SECTOR_PER_FAT * FAT_BYTE_PER_SECTOR * FAT_FAT_COUNT)
FAT_TABLE = []
for _ in range(FAT_FAT_COUNT):
    FAT_TABLE.append(FAT.CR(FAT_SECTOR_PER_FAT * FAT_BYTE_PER_SECTOR))

# print(FAT_ROOT_DIRENT)

def PDE(DE):
    assert len(DE.data) == 32
    FILE = {
        "DIR_NAME": DE.CR(8),
        "DIR_EXT":  DE.CR(3),
        "DIR_ATTR": DE.CRB(),
        "DIR_NTR":  DE.CRB(),
        "DIR_CRT":  DE.CRB(),
        "DIR_CRT":  DE.CRW(),
        "DIR_CRD":  DE.CRW(),
        "DIR_LAD":  DE.CRW(),
        "DIR_FCNH": DE.CRW(),
        "DIR_WT":   DE.CRW(),
        "DIR_WD":   DE.CRW(),
        "DIR_FCNL": DE.CRW(),
        "DIR_FS":   DE.CR(4)
    }
    if int(FILE["DIR_NAME"].RB()) == 0:
        return 0
    if int(FILE["DIR_NAME"].RB()) == 0xE5:
        return -1

    FILE["DIR_FCN"] = FILE["DIR_FCNL"] + FILE["DIR_FCNH"] 
    return FILE

def FILE_CONTENT(DATA, FILE):
    FILE_CIDX = FILE["FAT_CLUS"]
    FILE_CONTENT = ByteArray()
    for FILE_IDX in FILE_CIDX:
        # print(FILE_IDX)
        FILE_CONTENT += DATA.RR(FAT_BYTE_PER_CLUS, FAT_BYTE_PER_CLUS * (FILE_IDX) )
    return FILE_CONTENT

def GET_DIR_CHLD(DATA, FILE):
    if int(FILE['DIR_ATTR']) != 16:
        print("Not Directory.")
        return -1
    FC = FILE_CONTENT(DATA, FILE)
    FDR = []
    while (FDE := FC.CR(32)).data:
        if (FDF := PDE(FDE)): 
            FDR.append(FDF)
    return FDR
    
def PRINT_DIR(DE):
    FILE_NAME = str(DE["DIR_NAME"]) + (("." + str(DE["DIR_EXT"])) if str(DE["DIR_EXT"]) else "")
    FILE_TYPE = "f" if int(DE["DIR_ATTR"]) == 32 else "d" if int(DE["DIR_ATTR"]) == 16 else "."
    FILE_WT = int(DE["DIR_WT"])
    FILE_SIZE = int(DE["DIR_FS"])
    print(f"{FILE_TYPE} {FILE_NAME:<11} {FILE_SIZE:>6d}B {FILE_WT}") 

def LIST_DIR(DATA, DIRENT):
    print()
    print(f"Child of {str(DIRENT["DIR_NAME"])}")
    print(f"{len(FILES := GET_DIR_CHLD(DATA, DIRENT))}")
    for FILE in FILES:
        PRINT_DIR(FILE)
    print()
    return FILES

def FIND_FAT(FAT_TABLE, FAT_IDX):
    # FAT_IDX = int(FILE["DIR_FCN"])
    FAT_CLUS = []
    while True:
        FAT_CLUS.append(FAT_IDX - 2)
        FAT_IDX = FAT_TABLE[0][ FAT_IDX * 2 ]
        if int(FAT_IDX) == 255:
            break
    # print(FAT_CLUS)
    return FAT_CLUS

ISDIR = lambda FILE: int(FILE["DIR_ATTR"]) == 16

RDR = FS.CR(FAT_ROOT_DIRENT * 32)
DATA = FS.CR(FAT_SECT_COUNT * FAT_BYTE_PER_SECTOR - FS.read)

RDE = {"DIR_NAME": "/", "FAT_CLUS": [0], "DIR_ATTR": 16}
for F in (RDS := LIST_DIR(RDR, RDE)):
    F["FAT_CLUS"] = FIND_FAT(FAT_TABLE, int(F["DIR_FCN"]))
    if ISDIR(F): LIST_DIR(DATA, F)

def GET_FILE(DATA, PATH):
    CFP = RDS.copy()
    for FP in (PS := PATH.split("/"))[1:-1]:
        print(FP)
        for F in CFP:
            if str(F["DIR_NAME"]) == FP and ISDIR(F):
                CFP = GET_DIR_CHLD(DATA, F)
                break
    for F in CFP:
        if f"{str(F["DIR_NAME"])}.{str(F["DIR_EXT"])}" == PS[-1]:
            F["FAT_CLUS"] = FIND_FAT(FAT_TABLE, int(F["DIR_FCN"]))
            return FILE_CONTENT(DATA, F)

import os, sys
while True:
    FP = input("? ")
    if os.path.exists(FP.split("/")[-1]): exit()
    with open(FP.split("/")[-1], "wb") as f:
        f.write(GET_FILE(DATA, FP).data)