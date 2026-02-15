// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title JusticeVault
 * @author JusticeVault
 * @notice Decentralized legal evidence registry. Anchors document fingerprints on-chain and emits events for the AI Oracle to process.
 * @dev Uses OpenZeppelin AccessControl for Lawyer and Judge roles. Evidence is stored per case ID; Judges can validate after AI review.
 */
contract JusticeVault is AccessControl {
    bytes32 public constant JUDGE_ROLE = keccak256("JUDGE_ROLE");
    bytes32 public constant LAWYER_ROLE = keccak256("LAWYER_ROLE");

    /// @notice Single piece of evidence: fingerprint (hash), IPFS pointer, submitter, and validation status.
    struct Evidence {
        uint256 caseId;     /// @dev The case this evidence belongs to.
        bytes32 fileHash;   /// @dev SHA-256 fingerprint of the document; used for tamper detection.
        string ipfsCid;     /// @dev IPFS content identifier (CID) where the file is stored.
        address lawyer;    /// @dev Address that submitted this evidence.
        uint256 timestamp; /// @dev Block timestamp when submitted.
        bool isValidated;   /// @dev Set to true when a Judge calls validateEvidence.
    }

    /// @notice caseId => list of evidence. Public getter: caseRegistry(caseId, index).
    mapping(uint256 => Evidence[]) public caseRegistry;

    /// @notice Emitted when a Lawyer submits evidence. The Oracle listens for this to trigger download + AI summary.
    /// @param caseId The case identifier.
    /// @param fileHash The document fingerprint (SHA-256).
    /// @param ipfsCid The IPFS CID.
    /// @param lawyer The submitter's address.
    event EvidenceFiled(uint256 indexed caseId, bytes32 fileHash, string ipfsCid, address indexed lawyer);

    /// @notice Emitted when a Judge validates evidence (human-in-the-loop).
    /// @param caseId The case identifier.
    /// @param index Index of the evidence in caseRegistry[caseId].
    /// @param judge The Judge's address.
    event EvidenceValidated(uint256 indexed caseId, uint256 index, address indexed judge);

    /// @notice Sets the initial admin who can grant Lawyer and Judge roles.
    /// @param initialAdmin Address to receive DEFAULT_ADMIN_ROLE.
    constructor(address initialAdmin) {
        _grantRole(DEFAULT_ADMIN_ROLE, initialAdmin);
    }

    /**
     * @notice Submit a new piece of evidence for a case. Only callable by an address with LAWYER_ROLE.
     * @dev The hash must be the SHA-256 of the file stored at the given IPFS CID; the Oracle will verify this.
     * @param _caseId The case to attach this evidence to.
     * @param _fileHash The SHA-256 hash of the document (32 bytes).
     * @param _cid The IPFS CID string (e.g. "QmXoyp...").
     */
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

        emit EvidenceFiled(_caseId, _fileHash, _cid, msg.sender);
    }

    /**
     * @notice Mark a piece of evidence as validated after judicial review. Only callable by JUDGE_ROLE.
     * @dev Human-in-the-loop: the Judge confirms the evidence after reviewing the AI-generated brief.
     * @param _caseId The case ID.
     * @param _index The index of the evidence in caseRegistry[_caseId] (0-based).
     */
    function validateEvidence(uint256 _caseId, uint256 _index) external onlyRole(JUDGE_ROLE) {
        require(_index < caseRegistry[_caseId].length, "Evidence does not exist");

        Evidence storage evidence = caseRegistry[_caseId][_index];
        require(!evidence.isValidated, "Evidence already validated");

        evidence.isValidated = true;

        emit EvidenceValidated(_caseId, _index, msg.sender);
    }
}
