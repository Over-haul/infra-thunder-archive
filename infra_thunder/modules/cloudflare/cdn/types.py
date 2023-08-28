from enum import Enum


class RuleSSL(Enum):
    off = "off"
    flexible = "flexible"
    full = "full"
    strict = "strict"
    origin_pull = "origin_pull"


class CacheLevel(Enum):
    bypass = "bypass"
    basic = "basic"
    simplified = "simplified"
    aggressive = "aggressive"
    cache_everything = "cache_everything"


class Polish(Enum):
    off = "off"
    lossless = "lossless"
    lossy = "lossy"


class RecordType(Enum):
    A = "A"
    AAA = "AAAA"
    CAA = "CAA"
    CERT = "CERT"
    CNAME = "CNAME"
    DNSKEY = "DNSKEY"
    DS = "DS"
    LOC = "LOC"
    MX = "MX"
    NAPTR = "NAPTR"
    NS = "NS"
    PTR = "PTR"
    SMIMEA = "SMIMEA"
    SPF = "SPF"
    SRV = "SRV"
    SSHFP = "SSHFP"
    TLSA = "TLSA"
    TXT = "TXT"
    URI = "URI"
