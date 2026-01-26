// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

contract JusticeVault is AccessControl {
    bytes32 public constant JUDGE_ROLE = keccak256("JUDGE_ROLE");
    bytes32 public constant LAWYER_ROLE = keccak256("LAWYER_ROLE");

    // 1. The Evidence "Identity" Pattern
    struct Evidence {
        uint256 caseId;
        bytes32 fileHash;   // The "Fingerprint"
        string ipfsCid;     // The "Pointer" to IPFS
        address lawyer;     // Who submitted it
        uint256 timestamp;  // When it was filed
        bool isValidated;   // If a Judge confirmed it
    }

    // Storage for all evidence
    mapping(uint256 => Evidence[]) public caseRegistry;

    // 2. The "Oracle-Listener" Event
    // Python will "listen" for this specific name and arguments
    event EvidenceFiled(uint256 indexed caseId, bytes32 fileHash, string ipfsCid, address indexed lawyer);

    constructor(address initialAdmin) {
        _grantRole(DEFAULT_ADMIN_ROLE, initialAdmin);
    }

    // 3. The Function Lawyers will call
    function submitEvidence(uint256 _caseId, bytes32 _fileHash, string memory _cid) public onlyRole(LAWYER_ROLE) {
        Evidence memory newEvidence = Evidence({
            caseId: _caseId,
            fileHash: _fileHash,
            ipfsCid: _cid,
            lawyer: msg.sender,
            timestamp: block.timestamp,
            isValidated: false
        });

        caseRegistry[_caseId].push(newEvidence);

        // This triggers the Python AI summary
        emit EvidenceFiled(_caseId, _fileHash, _cid, msg.sender);
    }
}