# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from binascii import unhexlify
from logging import getLogger
from time import sleep
from traceback import format_exc
from zlib import crc32
import socket

from odoo.addons.hw_drivers.driver import Driver
from odoo.addons.hw_drivers.event_manager import event_manager
from odoo.addons.hw_drivers.iot_handlers.interfaces.SocketInterface import socket_devices

_logger = getLogger(__name__)

class IngenicoTagType():
    """Tag type Function.

    This class is used to make working with the provided Ingenico tags easier.
    Instances of this class should only be generated by the static list 
    provided by Ingenico.
    """
    def __init__(self, name, tag, tagFormat, tagLen):
        """
        Args:
            name (str): Human readable tag name.
            tag (b): Identification tag formated as a byteArray.
            tagformat (str): Format of the tag content.
                    * b: boolean values. Each boolean is 1 bit.
                    * a: ASCII characters
                    * i: Binari Code Decimals
                    * x: Hexadecimal digits
            tagLen (int): Length of the tag content. This value is always the numbers of bytes 
                    (This is not always the case in the official documentation provided by Ingenico!!)
        """
        self.name = name
        self.tag = tag
        self.format = tagFormat
        self.len = tagLen

    def getDict(self):
        """Get a dictionary with the tag

        Returns {
            name (str): tag name,
            tag (b): Tag identifier,
            tagLen (int): The length of the tag identifier,
            format (str): format of the tag content,
            len (int): Length of the tag content
            }
        """
        return {
                'name': self.name,
                'tag': self.tag,
                'tagLen': len(self.tag)/2,
                'format': self.format,
                'len': self.len,
                }

    def hasTag(self, tag):
        """Check if tag is equal

        Check if a tag is equal, regardless of the case of the characters. The case does not change anything 
        in hexadecimal, but comparing without upper/lower would still give false negatives.

        Returns True if equal
        """
        return tag.upper() == self.tag.upper()

class IngenicoMessage():
    """Base Class for Ingenico Messages.
    Use OutgoingIngenicoMessage or IncommingIngenicoMessage instead to initialize messages.

    _const: Most of these constants are provided by Ingenico and should not be changed. 
    """
    _const = type('',(),{ 
        'keepAliveInterval': b'\x50\x05',
        'magic' : b'P4Y-ECR!',
        'messageType' : {
            'HelloRequest'                      : b'\x00\x00\x00\x16',   #!< Request# a# connection# with# the# ECR.
            'HelloResponse'                 : b'\x00\x00\x00\x16',   #!< Result# of# the# connection# request.
            'KeepAliveRequest'                  : b'\x00\x00\x00\x18',   #!< Notification# of# status# and# keep-alive.
            'KeepAliveResponse'                 : b'\x00\x00\x00\x19',   #!< Result# of# the# notification.
            'ByeRequest'                    : b'\x00\x00\x00\x20',   #!< Request# to# terminate# the# connection.
            'ByeResponse'                   : b'\x00\x00\x00\x21',   #!< Result# of# terminate# connection# request.

            'AcquirerDownloadListRequest'       : b'\x00\x00\x00\x30',   # The# ECR# Requests# CTAP# to# give# a# list# with# available# acquirers# (used# to# select# one# for# an# acquirer# download)
            'AcquirerDownloadListResponse'      : b'\x00\x00\x00\x31',   # CTAP# sends# the# ECR# a# list# of# available# acquirers# (used# to# select# one# for# an# acquirer# download)
            'AcquirerDelMsgListRequest'         : b'\x00\x00\x00\x32',   # The# ECR# Requests# CTAP# to# give# a# list# with# available# acquirers# (used# to# select# one# for# an# acquirer# download)
            'AcquirerDelMsgListResponse'        : b'\x00\x00\x00\x33',   # CTAP# sends# the# ECR# a# list# of# available# acquirers# (used# to# select# one# for# an# acquirer# download)
            'AcquirerDelMsgRequest'             : b'\x00\x00\x00\x34',   # The# ECR# Requests# CTAP# to# give# a# list# with# available# acquirers# (used# to# select# one# for# an# acquirer# download)
            'AcquirerDelMsgResponse'            : b'\x00\x00\x00\x35',   # CTAP# sends# the# ECR# a# list# of# available# acquirers# (used# to# select# one# for# an# acquirer# download)
            'PerformAcqDownLoadRequest'         : b'\x00\x00\x00\x36',   
            'PerformAcqDownLoadResponse'        : b'\x00\x00\x00\x37',   
            'SecuritySchemeListRequest'         : b'\x00\x00\x00\x38',   # The# ECR# Requests# CTAP# to# give# a# list# with# available# security-schemes# (used# to# select# one# for# an# security-scheme# download)
            'SecuritySchemeListResponse'        : b'\x00\x00\x00\x39',   # CTAP# sends# the# ECR# a# list# of# available# security-schemes# (used# to# select# one# for# an# security-scheme# download)
            'PerformKeyLoadRequest'             : b'\x00\x00\x00\x40',
            'PerformKeyLoadResponse'            : b'\x00\x00\x00\x41',

            'PrintInfoRequest'              : b'\x00\x00\x00\x46',
            'PrintInfoResponse'             : b'\x00\x00\x00\x47',
            'TransactionRequest'        : b'\x00\x00\x00\x48',   #!< Request# to# perform# a# transaction.
            'TransactionResponse'       : b'\x00\x00\x00\x49',   #!< Result# of# the# transaction.
            'TotalsRequest'         : b'\x00\x00\x00\x50',   #!< Request# an# overview# of# the# counters# (print# on# terminal# or# send# to# ECR).
            'TotalsResponse'                : b'\x00\x00\x00\x51',   #!< Result# of# the# totals# request.
            'LastTicketRequest'             : b'\x00\x00\x00\x52',   #!< Request# the# last# ticket# (print# on# terminal# or# send# to# ECR).# (Was# called# print# request# in# IDD).
            'LastTicketResponse'        : b'\x00\x00\x00\x53',   #!< Result# of# the# last# ticket# request.# (Was# called# print# response# in# IDD).
            'CancelRequest'         : b'\x00\x00\x00\x54',   #!< Request# the# cancellation# of# an# on-going# operation.
            'CancelResponse'                : b'\x00\x00\x00\x55',   #!< Result# of# the# cancellation# request.
            'LastTransactionRequest'            : b'\x00\x00\x00\x56',   #!< Request# the# result# of# the# last# transaction.
            'LastTransactionResponse'           : b'\x00\x00\x00\x57',   #!< Result# of# the# last# transaction# request.
            'PrintConfirmationRequest'          : b'\x00\x00\x00\x64',   #!< Print# confirmation# from# ECR# to# terminal# when# a# card# holder# ticket# must# be# printed# on# the# ECR.
            'PrintConfirmationResponse'         : b'\x00\x00\x00\x65',   #!< Print# confirmation# from# ECR# to# terminal# when# a# card# holder# ticket# must# be# printed# on# the# ECR.
            'PrintRequest'          : b'\x00\x00\x00\x66',   #!< Request# to# print# some# data# (e.g.# ECR# ticket)# on# the# terminal# printer.# (ECR# does# not# need# a# printer# then)# (this# message# is# not# in# IDD).
            'PrintResponse'         : b'\x00\x00\x00\x67',   #!< Result# of# the# print# request# (this# message# is# not# in# IDD).
            'IntermediateResultRequest'         : b'\x00\x00\x00\x68',   #!< Request# with# the# intermediate# result.
            'IntermediateResultResponse'    : b'\x00\x00\x00\x69',   #!< Result# of# the# intermediate# result# request# (continue/abort# transaction).
            'InformationReport'             : b'\x00\x00\x00\x80',   #!< Report# the# progress# of# a# transaction# and# other# information# like# merchant# messages.
            'SettingsRequest'               : b'\x00\x00\x00\x82',   #!< Change# one# or# more# settings# in# the# terminal.
            'SettingsResponse'              : b'\x00\x00\x00\x83',   #!< Result# of# the# change# settings# request.
            'VersionInformationRequest'         : b'\x00\x00\x00\x90',   #!< Request# the# version# of# the# terminal# software
            'VersionInformationResponse'    : b'\x00\x00\x00\x91',   #!< Result# of# the# version# request.
            'PerformTmsSessionReuqest'          : b'\x00\x00\x00\x92',
            'PerformTmsSessionResponse'         : b'\x00\x00\x00\x93',
            'RebootAndClearCtapDataBaseRequest' : b'\x00\x00\x01\x00',  # there# is# no# response# on# this# command:# the# terminal# will# reboot

            # Transparent# mode# messages.
            'TmTransparentModeRequest'          : b'\x00\x00\x10\x00', #!< Request# to# start# or# stop# transparent# mode.
            'TmTransparentModeResponse'         : b'\x00\x00\x10\x01', #!< Result# of# the# request# to# start# or# stop# transparent# mode.
            'TmUiControlRequest'            : b'\x00\x00\x10\x02', #!< Request# to# update# the# user# interface# (buzzer,# display,# LEDs)# when# in# transparent# mode.
            'TmUiControlResponse'           : b'\x00\x00\x10\x03', #!< Result# of# the# UI# request.
            'TmAuthenticateRequest'         : b'\x00\x00\x10\x04', #!< Request# to# authenticate# to# the# card# when# in# transparent# mode.
            'TmAuthenticateResponse'            : b'\x00\x00\x10\x05', #!< Result# of# the# authenticate# request.
            'TmReadCardDataRequest'         : b'\x00\x00\x10\x06', #!< Request# to# read# data# from# the# card# when# in# transparent# mode.
            'TmReadCardDataResponse'            : b'\x00\x00\x10\x07', #!< Result# of# the# read# card# data# request.
            'TmWriteCardDataRequest'            : b'\x00\x00\x10\x08', #!< Request# to# write# data# to# the# card# when# in# transparent# mode.
            'TmWriteCardDataResponse'           : b'\x00\x00\x10\x09', #!< Result# of# the# write# card# data# request.
            'TmStatusRequest'               : b'\x00\x00\x10\x10', #!< Request# the# status# of# the# transparent# mode.
            'TmStatusResponse'              : b'\x00\x00\x10\x11', #!< Result# of# the# status# request.
            },
        'tagType' : [
            IngenicoTagType( 'None'                         , '00'     , ''     ,False ),
            # Header, body, footer primitive tags.
            IngenicoTagType( 'TransactionStage'             , '0E'     , 'x'   , 1 ),
            IngenicoTagType( 'StageMessage'                 , '0F'     , 'a'   , False ),
            IngenicoTagType( 'ProtocolId'               , '10'     , 'i'   , 4 ),
            IngenicoTagType( 'MessageType'              , '11'     , 'i'   , 4 ),
            IngenicoTagType( 'TerminalId'               , '12'     , 'a'   , False ),
            IngenicoTagType( 'EcrId'                    , '13'     , 'a'   , False ),
            IngenicoTagType( 'SequenceNumber'               , '14'     , 'x'   , 2 ),
            IngenicoTagType( 'KeepAliveReason'              , '15'     , 'x'   , 1 ),
            IngenicoTagType( 'ResultCode'               , '16'     , 'x'   , 2 ),
            IngenicoTagType( 'ByeReason'                , '17'     , 'x'   , 1 ),
            IngenicoTagType( 'Language'                     , '18'     , 'a'   , False ),
            IngenicoTagType( 'TerminalState'                , '19'     , 'b'   , 8 ),
            IngenicoTagType( 'TransactionId'                , '1A'     , 'x'   , 8 ),
            IngenicoTagType( 'PrintResult'              , '1B'     , ''    , False ),
            IngenicoTagType( 'Mdc'                  , '1C'     , 'x'   , False ),
            IngenicoTagType( 'MerchantText'             , '1D'     , 'a'   , False ),
            IngenicoTagType( 'CancelReason'             , '1E'     , 'x'    , 1 ),

            # Communication parameter group tags.
            IngenicoTagType( 'IpAddress'                    , '40'     , ''    , False ),
            IngenicoTagType( 'PortNumber'               , '41'     , ''    , False ),

            # Connection parameters groups tags.
            IngenicoTagType( 'ConnectionTimeout'            , '47'     , ''    , False ),
            IngenicoTagType( 'ConnectionRetries'            , '48'     , ''    , False ),
            IngenicoTagType( 'KeepAliveInterval'            , '49'     , 'i'   , 2 ),

            # Ticket data group tags.
            IngenicoTagType( 'TicketType'                   , '4A'     , 'x'   , False ),
            IngenicoTagType( 'TicketHeader'             , '4B'     , ''    , False ),
            IngenicoTagType( 'TicketBody'               , '4C'     , 'a'   , False ),
            IngenicoTagType( 'TicketFooter'             , '4D'     , ''    , False ),

            # Print data group.
            IngenicoTagType( 'PrintOrigin'                  , '4E'     , ''    , False ),
            IngenicoTagType( 'PaperWidth'               , '4F'     , ''    , False ),

            # Transaction (information) group tags.
            IngenicoTagType( 'Amount'                   , '50'     , 'i'   , 4 ),
            IngenicoTagType( 'CurrencyCode'             , '51'     , 'i'   , 4 ),
            IngenicoTagType( 'CurrencyExponent'             , '52'     , 'i'   , 2 ),   # Named Decimal in IDD.
            IngenicoTagType( 'ProgressReportLanguage'       , '53'     , 'a'   , 2 ),
            IngenicoTagType( 'TransactionType'          , '54'     , ''    , False ),
            IngenicoTagType( 'MerchantTransactionReference' , '55'     , ''    , False ),
            IngenicoTagType( 'TransactionResult'        , '56'     , ''    , False ),
            IngenicoTagType( 'TransactionDateTime'      , '57'     , ''    , False ),
            IngenicoTagType( 'IntermediateResultMode'       , '58'     , ''    , False ),
            IngenicoTagType( 'TransactionMode'          , '59'     , ''    , False ),
            IngenicoTagType( 'AuthorisationCode'        , '1F70'   , ''    , False ),
            IngenicoTagType( 'Token'                , '1F71'   , ''    , False ),

            # Settings# (result) group.
            IngenicoTagType( 'SettingId'                , '5A'     , ''    , False ),
            IngenicoTagType( 'SettingType'              , '5B'     , ''    , False ),
            IngenicoTagType( 'SettingValue'             , '5C'     , ''    , False ),
            IngenicoTagType( 'SettingResult'                , '5D'     , ''    , False ),
            IngenicoTagType( 'TotalsType'               , '5F54'   , ''    , False ),
            IngenicoTagType( 'InfoType'                     , '5F55'   , ''    , False ),

            # Version information tags.
            IngenicoTagType( 'ApplicationId'                , '80'     , ''    , False ),
            IngenicoTagType( 'LogicalId'                , '81'     , 'a'   , False ),
            IngenicoTagType( 'SerialNumber'             , '82'     , 'a'   , False ),
            IngenicoTagType( 'VersionNumber'                , '83'     , ''    , False ),
            IngenicoTagType( 'VersionString'            , '84'     , ''    , False ),
            IngenicoTagType( 'ExtraInformationName'     , '85'     , ''    , False ),
            IngenicoTagType( 'ExtraInformationValue'        , '86'     , ''    , False ),
            IngenicoTagType( 'ExtraInformationUnit'     , '87'     , ''    , False ),

            # Group tags.
            IngenicoTagType( 'Group_EncryptionParameters'   , 'A0'     , 'GRP' , False ),
            IngenicoTagType( 'Group_CommunicationParameters', 'A1'     , 'GRP' , False ),
            IngenicoTagType( 'Group_SupportedLanguages'     , 'A2'     , 'TBL' , False ),
            IngenicoTagType( 'Group_TransactionData'        , 'A3'     , 'GRP' , False ),
            IngenicoTagType( 'Group_ConnectionParameters'   , 'A4'     , 'GRP' , False ),
            IngenicoTagType( 'Group_PrintData'          , 'A5'     , 'GRP' , False ),
            IngenicoTagType( 'Group_TicketData'         , 'A6'     , 'GRP' , False ),
            IngenicoTagType( 'Group_ExtraInformation'       , 'A7'     , 'GRP' , False ),
            IngenicoTagType( 'Group_TransactionInformation' , 'A8'     , 'GRP' , False ),
            IngenicoTagType( 'Group_TcpParameter'       , 'A9'     , 'GRP' , False ),
            IngenicoTagType( 'Group_UsbParameters'      , 'AA'     , 'GRP' , False ),
            IngenicoTagType( 'Group_SerialParameters'       , 'AB'     , 'GRP' , False ),
            IngenicoTagType( 'Group_Settings'           , 'AC'     , 'GRP' , False ),
            IngenicoTagType( 'Group_SettingsResult'     , 'AD'     , 'GRP' , False ),

            # General group tags.
            IngenicoTagType( 'Group_Header'                 , 'E1'     , 'GRP' , False ),
            IngenicoTagType( 'Group_Body'               , 'E2'     , 'GRP' , False ),
            IngenicoTagType( 'Group_Footer'             , 'E3'     , 'GRP' , False ),
            IngenicoTagType( 'Group_TableRecord'            , 'EF'     , 'REC' , False ),   # Used for repeated fields. e.g. The ticket data tag contains for each ticket a table record tag.
            IngenicoTagType( 'Group_Root'                   , 'F0'     , 'GRP' , False ),

            # Transparent mode tags.
            IngenicoTagType( 'TmTransparentMode'            , '1F01'   , ''    , False ),
            IngenicoTagType( 'TmCardDetectionTimeout'       , '1F02'   , ''    , False ),
            IngenicoTagType( 'TmCardUid'            , '1F10'   , ''    , False ),
            IngenicoTagType( 'TmCardAtr'            , '1F11'   , ''    , False ),
            IngenicoTagType( 'TmCardType'           , '1F12'   , ''    , False ),

            # Transparent mode UI Control tags.
            IngenicoTagType( 'TmDisplayText'                , '1F20'   , ''    , False ),
            IngenicoTagType( 'TmBeepType'               , '1F21'   , ''    , False ),
            IngenicoTagType( 'TmLedControl'             , '1F22'   , ''    , False ),

            # Transparent mode authentication/read data/writ,.
            IngenicoTagType( 'TmKey'                    , '1F30'   , ''    , False ),
            IngenicoTagType( 'TmAddress'                , '1F31'   , ''    , False ),
            IngenicoTagType( 'TmDataSize'               , '1F32'   , ''    , False ),
            IngenicoTagType( 'TmData'                       , '1F33'   , ''    , False ),

            # Transparent mode groups.
            IngenicoTagType( 'Group_TmTransparentMode'      , '3F01'   , ''    , False ),
            IngenicoTagType( 'Group_TmUiControl'        , '3F02'   , ''    , False ),
            IngenicoTagType( 'RebootAndClearType'       , 'C1'     , ''    , False ),
            IngenicoTagType( 'SendOrDelete'         , 'C2'     , ''    , False ),     # used# for# pending# messages# :# 1=send# 2=delete
            IngenicoTagType( 'Group_AcquirerList'       , 'E7'     , ''    , False ),     # group: AcquirerIdentifier=0xDF68, AcquirerLabelName=0xDF69
            IngenicoTagType( 'Group_SecuritySchemeList'     , 'BF01'   , ''    , False ),   # group: SecuritySchemeIdentifier=0xDF6A, SecuritySchemeLabelName=0xDF6B
            IngenicoTagType( 'CardholderLanguage'       , 'DF1A'   , ''    , False ),
            IngenicoTagType( 'Card_Brand_Identifier'        , 'DF5F'   , 'i'    , 2 ),
            IngenicoTagType( 'SecuritySchemeIdentifier'     , 'DF8204' , ''    , False ),
            IngenicoTagType( 'AcquirerIdentifier'       , 'DF68'   , ''    , False ),
            IngenicoTagType( 'AcquirerLabelName'        , 'DF69'   , ''    , False ),
            ],
        'transactionStage' : {
            b'\x00'   :               'None',
            b'\x01'   :               'WaitingForCard',
            b'\x02'   :               'WaitingForPin',
            b'\x03'   :               'WaitingForTransaction',
            b'\x04'   :               'Finished',
            b'\x05'   :               'WaitingForTipInput',
            b'\x06'   :               'WaitingForConfirmationService',
            b'\x07'   :               'WaitingForConfirmationAmount',
            b'\x08'   :               'WaitingForConfirmationServiceAndAmount',
            b'\x09'   :               'WaitingForCardRemoval',
            b'\x0a'  :               'WaitingForLastTransactionResult',
            b'\x0b'  :               'WaitingForApplicationSelection',
            b'\x0c'  :               'CardDetected',
            b'\x0d'  :               'WaitingForIntermediateResult',
            b'\x0e'  :               'CardRemoved',
            },
        'transactionResult' : {
            b'\x00'   :               'Approved',
            b'\x01'   :               'Error',
            b'\x02'   :               'Declined',
            b'\x03'   :               'Stopped',
            b'\x04'   :               'TechnicalProblem',
            b'\x05'   :               'TransparentMode',
            },
        'cancelReasons' : {
            'manual'        :   b'\x00',
            'system'        :   b'\x01',
            },
        'byeReasons' : {
            'Deactivate'    :   b'\x01',
            'Shutdown'      :   b'\x02',
            'Reboot'        :   b'\x03',
            'Reconnect'     :   b'\x04',
            'BatteryEmpty'  :   b'\x05',
            },
        })()

    @classmethod
    def _getTagDetailsByCode(cls, tagCode):
        """Search for tag in _const using the hex identifier.

        Returns InenicoTagType instance.

        Args:
            tagCode (b): hexadecimal identifier of tag.
        """
        return next((tagType for tagType in cls._const.tagType if tagType.hasTag(tagCode) == True), None)

    @classmethod
    def _getTagDetailsByName(cls, tagName):
        """Search for tag in _const providing the Human readable name.

        Returns InenicoTagType instance.

        Args:
            tagCode (b): hexadecimal identifier of tag.
        """
        return next((tagType for tagType in cls._const.tagType if tagType.name == tagName), None)

    def __init__(self, dev):
        """Base Initialisation of Ingenico Message.

        Args:
            dev (Obj): tcp socket (or other device with byte-based send and recv function)
        """
        self.dev = dev

class OutgoingIngenicoMessage(IngenicoMessage):
    
    @staticmethod
    def _withLength(msg, length):
        """Return tag content with given length.

        Some tags have to have a fixed length to be accepted by the payment terminal. This function will add null-bytes
        to match the required length.

        Args:
            msg (b): the message to edit
            length (int): wanted length
        """
        try:
            toAdd = length - len(msg)
        except:
            _logger.error(format_exc())

        if toAdd > 0:
            return b'\x00' * toAdd + msg
        return msg

    @staticmethod
    def _getCRC32(msg):
        """Return the crc for the specified message as a bytestring.

        The result will always be 4 bytes long.

        Args:
            msg (b): the message to calculate the CRC for
        """
        return unhexlify('{:08x}'.format(crc32(msg)))

    @classmethod
    def _generateTag(cls, tagName, content):
        """Return formatted tag with tag identifier + length + content.

        The content of a tag often includes other tags, these have to be already formatted.
        
        Args:
            tagName (str): Human readable tag name
            content (b): formatted tag content
        """

        tag = cls._getTagDetailsByName(tagName)
        if tag.len:
            return unhexlify(tag.tag) + chr(tag.len).encode() + cls._withLength(content, tag.len)
        return unhexlify(tag.tag) + chr(len(content)).encode() + content

    @classmethod
    def _generateMsg(cls, header, body, footer):
        """Return The formatted outgoing message including MessageLength and Magic string.

        This is the very last step of the message generation. All arguments have to be completely formatted.

        Args:
            header (b)
            body (b)
            footer (b)
        """
        root = cls._generateTag("Group_Root", header + body + footer)
        msgLength = (len(cls._const.magic + root)).to_bytes(3, byteorder='big')
        while len(msgLength) < 4:
            msgLength = b'\x00' + msgLength
        return msgLength + cls._const.magic + root

    def __init__(self, dev, terminalId, ecrId, protocolId, messageType, sequence, **kwargs):
        """Initialisation of Outgoing Ingenico messages.

        After initialisation the message will be automatically generated. the send function can be called to send the 
        message to the device.

        Args:
            dev (Obj): tcp socket (or other device with byte-based send and recv function)
            protocolId
            messageType

        Kwargs:
            keepAliveInterval
            keepAliveResult
            resultCode
            transactionId
            amount
            reason
        """
        super().__init__(dev)

        self.terminalId = terminalId
        self.ecrId = ecrId
        self.protocolId = protocolId
        messageTypes = self._const.messageType
        self.messageTypeId = messageTypes[messageType]
        self.sequence = sequence
        self.resultCode = b'\x00'

        if messageType in ["CancelRequest", "ByeRequest", "KeepAliveResponse"]:
            self.reason = kwargs["reason"]
        elif messageType == "HelloResponse":
            self.keepAliveInterval = self._const.keepAliveInterval
        elif messageType == "LastTransactionStatusRequest":
            self.transactionId = kwargs["transactionId"]
        elif messageType == "TransactionRequest":
            self.transactionId = kwargs["transactionId"]
            self.amount = kwargs["amount"]

        header = self._generateHeader()
        body, mdc = self._generateBody(self.messageTypeId)
        footer = self._generateFooter(mdc)
        self.message = self._generateMsg(header, body, footer)

        self.send()

    def _generateHeader(self):
        """Return formatted header.

        The header does not depend on the message type.
        """
        return self._generateTag( "Group_Header",
                self._generateTag( "ProtocolId", self.protocolId) +
                self._generateTag( "MessageType", self.messageTypeId) +
                self._generateTag( "TerminalId", self.terminalId) +
                self._generateTag( "EcrId", self.ecrId.encode()) +
                self._generateTag( "SequenceNumber", self.sequence)
                )

    def _generateFooter(self, mdc):
        """Return the formatted footer

        The footer can only be created after the body has been generated. 

        Args:
            mdc (b): The Modification Detection Code generated on the Body tag.
        """
        return self._generateTag( "Group_Footer", mdc)

    def _generateMDC(self, innerBody):
        """Return the Modification Detection Code needed to generate the footer.

        This function gets called after generating the body and before generating the footer.

        Args:
            innerBody (b): formatted body excluding body-tag and length.
        """
        return self._generateTag("Mdc", self._getCRC32(innerBody))

    def _generateBody(self, messageTypeId):
        """Return formatted body and Modification Detection Code.

        Args:
            messageTypeId (b): Hexadecimal message type identifier.
        """
        innerBody = b''
        messageTypes = self._const.messageType
        if messageTypeId == messageTypes["HelloResponse"]:
            innerBody = self._generateTag( "ResultCode", self.resultCode) + \
                self._generateTag( "Group_ConnectionParameters", 
                        self._generateTag( "KeepAliveInterval", self.keepAliveInterval,))
        elif messageTypeId == messageTypes["KeepAliveResponse"]:
            innerBody = self._generateTag( "KeepAliveReason", self.reason) + \
                self._generateTag( "ResultCode", self.resultCode)
        elif messageTypeId == messageTypes["TransactionRequest"]:
            innerBody = self._generateTag( "TransactionId", 
                unhexlify('{:016x}'.format(int(self.transactionId)))) +\
                        self._generateTag( "Group_TransactionData", self._generateTag( "Amount" , 
                            int(str(self.amount), 16).to_bytes(4, byteorder='big'))) +\
                                    self._generateTag( "Group_PrintData", self._generateTag( "PrintOrigin",b'\x02'))
        elif messageTypeId == messageTypes["CancelRequest"]:
            innerBody = self._generateTag( "CancelReason", self._const.cancelReasons[self.reason])
        return self._generateTag( "Group_Body", innerBody), self._generateMDC(innerBody)

    def send(self):
        """Send the generated message to the device.

        This is the only function that has to be called manually!
        """
        self.dev.send(self.message)

class IncommingIngenicoMessage(IngenicoMessage):

    @staticmethod
    def _bcdToInt(byteArray):
        """Return an integer from a binary coded decimal.

        Args:
            byteArray (b): Binary Coded Decimal (https://www.electronics-tutorials.ws/binary/binary-coded-decimal.html)
        """
        return int.from_bytes(byteArray, byteorder='big')

    def _getMsg(self, length ):
        """Return a dictionary of the next tag in the buffer.

        Returns the decoded content of an message tag. If the tag is an group of other tags, this function will get
        called again to generate an dictionary of the entire message tree.

        Returns length left in parent tag.

        Args:
            length (int): length left to be read in the parent tag.
        """
        tag = self._getTag()
        tag['len'], lengthBytes = self._getLength()
        if tag['format'] in ['GRP', 'TBL', 'REC']:
            xTags = {}
            xMsgLength = tag['len']
            while xMsgLength > 0:
                xTag, xMsgLength = self._getMsg(xMsgLength)
                xTags[xTag['name']] = xTag['msg']
            tag["msg"] = xTags
        else:
            tag["msg"] = self.dev.recv(tag['len'])
        return tag, length - (tag['len'] + lengthBytes +tag['tagLen'] )

    def __init__(self, dev):
        """Initialisation of incomming Ingenico messages.

        After initialisation there will be a check if there is an Ingenico message available. If so, the message will
        be requested from the socket buffer and will be decoded. The data will be made available in the variable 
        _tagTree

        All data is read directly from the device buffer. It is from upmost importance to call the read functions in the
        correct sequence. The messages from Ingenico have the Tag Length Value format. Becouse the mixed content of the
        messages the standard Python TLV library cannot be used to decode the messages. 

        Raises:
            ValueError: If the `Magic String` is not found an error will be thrown indicating the received message is
                no Ingenico message.

        Args:
            dev (Obj): tcp socket (or other device with byte-based send and recv function)
        """
        super().__init__(dev)

        # Receive message length and reduce it with length of magic string
        length = self._bcdToInt(self.dev.recv(4)) - 8
        # Check if message is from Ingenico terminal by comparing magic string
        self.magic = self.dev.recv(8)
        if self.magic and self.magic == self._const.magic:
            # Receive and decode message
            self._tagTree, leftLength = self._getMsg(length)
        else:
            _logger.warning('Out of magic!')

    def _getLength(self):
        """Return the message length of the tag

        The length is read directly from the device buffer. It is important to call this function only after receiving 
        the tag identifier.
        """
        length = int(self.dev.recv(1).hex(), 16)
        if (length//128 == 1):
            return int(self.dev.recv(length%128).hex(), 16), length%128
        else:
            return length, 1

    def _getTag(self):
        """Return the tag identifier

        The tag identifier is read directly from the device buffer.
        """
        tagLength = 1
        tag = self.dev.recv(1).hex()
        if int(tag, 16) % 32 == 31:
            getNext = True
            while (getNext):
                tagLength += 1
                nextByte = self.dev.recv(1).hex()
                if (int(nextByte, 16) < 128):
                    getNext = False
                tag += nextByte
        tagObject = self._getTagDetailsByCode(tag)
        return tagObject.getDict()

    def getProtocolId(self):
        """Return The Protocol Id from the tagtree.
        """
        return self._tagTree['msg']['Group_Header']['ProtocolId']

    def getTerminalId(self):
        """Return The Protocol Id from the tagtree.
        """
        return self._tagTree['msg']['Group_Header']['TerminalId']

    def getTransactionResult(self):
        """Return The Protocol Id from the tagtree.
        """
        if 'TransactionResult' in self._tagTree['msg']['Group_Body'].keys():
            return self._const.transactionResult[self._tagTree['msg']['Group_Body']['TransactionResult']]
        return False

    def getTransactionStage(self):
        """Return The Transaction Stage from the tagtree.

        If the transaction stage is not found return False.
        """
        if 'TransactionStage' in self._tagTree['msg']['Group_Body'].keys():
            return self._const.transactionStage[self._tagTree['msg']['Group_Body']['TransactionStage']]
        return False

    def getTransactionTicket(self):
        """Return The Transaction ticket from the tagtree.

        If there is no ticket data available return False.
        """
        if 'Group_TicketData' in self._tagTree['msg']['Group_Body'].keys() \
                and 'Group_TableRecord' in self._tagTree['msg']['Group_Body']['Group_TicketData'].keys():
            return self._tagTree['msg']['Group_Body']['Group_TicketData']['Group_TableRecord']['TicketBody']
        return False

    def getKeepAliveInterval(self):
        """Return the keep alive interval from the tagtree.
        
        If there is connection data available return False.
        """
        if 'Group_ConnectionParameters' in self._tagTree['msg'].keys():
            return self._tagTree['msg']['Group_ConnectionParameters']['KeepAliveInterval']
        return False

    def getKeepAliveReasonId(self):
        """Return The keep alive reason from the tagtree.

        If the message is no keep alive message return False.
        """
        if 'KeepAliveReason' in self._tagTree['msg']['Group_Body'].keys():
            return self._tagTree['msg']['Group_Body']['KeepAliveReason']
        return False

    def getMessageType(self):
        """Return The message type from the constants, as found in the tagtree.
        """
        messageTypeId = self._tagTree['msg']['Group_Header']['MessageType']
        return next((mt for mt, mtId in self._const.messageType.items() if mtId == messageTypeId and not mt == "HelloResponse" ), None)


class IngenicoDriver(Driver):
    connection_type = 'socket'
    _ecrId = 'odoo'

    def __init__(self, identifier, device):
        super(IngenicoDriver, self).__init__(identifier, device)
        self.dev = device.dev
        self._terminalId = device.terminalId
        self._protocolId = device.protocolId
        self._sequence = 0
        self.device_type = 'payment'
        self.device_connection = 'network'
        self.device_name = 'Ingenico payment terminal'
        self.device_manufacturer = 'Ingenico'
        self.cid = None

        self._actions.update({
            '': self._action_default,
        })

    @classmethod
    def supported(cls, device): 
        """Try to initialize a connection with the payment terminal.
        Override
        """
        try:
            # Setup socket connection
            msg = IncommingIngenicoMessage(device.dev)
            if msg and msg.magic == b'P4Y-ECR!' and msg.getMessageType() == "HelloRequest":
                device.terminalId = msg.getTerminalId()
                device.protocolId = msg.getProtocolId()
                OutgoingIngenicoMessage( device.dev, device.terminalId, cls._ecrId, device.protocolId, "HelloResponse", b'\x00')
                return True
            return False
        except Exception:
            _logger.error(format_exc())
            return False

    def disconnect(self):
        del socket_devices[self.device_identifier]
        super(IngenicoDriver, self).disconnect()

    def _getSequence(self):
        """Returns the sequence number for the next outgoing message.

        The sequence of incomming and outgoing messages are unrelated. If the sequence of outgoing messages is wrong
        the terminal will automatically close the connection.
        """
        self._sequence += 1
        return (self._sequence%(256**2)).to_bytes(2,byteorder='big')

    def _outgoingMessage(self, messageType, **kwargs):
        """Base function to generate in instance of OutgoingIngenicoMessage.
        """
        OutgoingIngenicoMessage( self, self._terminalId, self._ecrId, 
                self._protocolId, messageType, self._getSequence(), **kwargs)

    def _action_default(self, data):
        """Action trigered on request from Odoo.
        Override
        """
        try:
            self.data["Ticket"] = False
            if data['messageType'] == 'Transaction':
                self.cid = data['cid']
                self._outgoingMessage( "TransactionRequest", transactionId=data['TransactionID'], amount=data['amount'])
            elif data['messageType'] == 'Cancel':
                self._outgoingMessage( "CancelRequest", reason=data['reason'])
        except Exception:
            _logger.error(format_exc())

    def recv(self, length):
        try:
            return self.dev.recv(length)
        except socket.error:
            _logger.error(socket.error)

    def send(self, request):
        try:
            return self.dev.send(request)
        except socket.error:
            _logger.error(socket.error)

    def run(self):
        """If an payment terminal is found, start listening for messages from the terminal.
        Override
        """
        try:
            self.data = {'value': '', 'Stage': False, 'Response': False, 'Ticket': False, 'Error': False}
            while not self._stopped.isSet():
                sleep(1)
                msg = IncommingIngenicoMessage(self)
                if msg:
                    self.data['value'] = 'Connected'
                    self.data["Response"] = False
                    self.data["Error"] = False
                    msgType = msg.getMessageType()
                    if msgType == "KeepAliveRequest":
                        self._outgoingMessage( "KeepAliveResponse", reason=msg.getKeepAliveReasonId())
                    elif msgType == "TransactionResponse":
                        self.data["Response"] = msg.getTransactionResult() if msg.getTransactionResult() else self.data["Response"]
                        if self.data["Response"] == 'Error':
                            self.data["Error"] = 'Canceled'
                        self.data["Ticket"] = msg.getTransactionTicket() if msg.getTransactionTicket() else self.data["Ticket"]
                    self.data['Stage'] = msg.getTransactionStage() if msg.getTransactionStage() else self.data['Stage']
                    self.data['cid'] = self.cid
                event_manager.device_changed(self)
        except Exception:
            self.disconnect()
            _logger.error(format_exc())
