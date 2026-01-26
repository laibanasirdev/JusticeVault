// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "forge-std/Script.sol";
import {JusticeVault} from "../contracts/JusticeVault.sol";

contract DeployJusticeVault is Script {
    function run() external {
        // Use one of the private keys from your Anvil terminal
        uint256 deployerPrivateKey = 0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6;
        
        vm.startBroadcast(deployerPrivateKey);

        // Deploy the contract and set the deployer as the first admin
        new JusticeVault(vm.addr(deployerPrivateKey));

        vm.stopBroadcast();
    }}
