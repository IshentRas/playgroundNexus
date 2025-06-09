# Overview

```mermaid
---
config:
  layout: dagre
---
flowchart TD
  Start[Start Manual Tag Promotion] --> CheckTagExist{Is Release Candidate Tag Already Present in Target?};

  CheckTagExist -- Yes --> StopDuplicate[Stop - Tag Already Exists];
  CheckTagExist -- No --> RequestSourceAccess(Manual: Request Source EME/Sandbox Access);

  RequestSourceAccess --> SourceAccessApproved{Source Access Approved?};
  SourceAccessApproved -- No --> AbortSourceAccess[Abort: Access Denied];
  SourceAccessApproved -- Yes --> ExtractAndValidate[Manual: Extract & Validate Objects from Source EME/Sandbox];

  ExtractAndValidate --> AllObjectsGood{All Objects Validated?};
  AllObjectsGood -- No --> AbortValidation[Abort: Object Discrepancy];
  AllObjectsGood -- Yes --> CreateAndPushArtifact[Create & Push Artifact];

  CreateAndPushArtifact --> RequestTargetAccess(Manual: Request Target Server Access for Integrity);
  RequestTargetAccess --> TargetAccessApproved{Target Access Approved?};
  TargetAccessApproved -- No --> AbortTargetAccess[Abort: Access Denied];
  TargetAccessApproved -- Yes --> VerifyArtifact[Manual: Verify Artifact Integrity on Target];

  VerifyArtifact --> IntegrityOK{Artifact Integrity Verified?};
  IntegrityOK -- No --> AbortCorrupted[Abort: Corrupted Artifact];
  IntegrityOK -- Yes --> LoadArtifactTargetEME[Load Artifact to Target EME];

  LoadArtifactTargetEME --> RequestSandboxAccess(Manual: Request Target Sandbox Access);
  RequestSandboxAccess --> SandboxAccessApproved{Sandbox Access Approved?};
  SandboxAccessApproved -- No --> AbortSandboxAccess[Abort: Access Denied];
  SandboxAccessApproved -- Yes --> ManualBackupCheckout[Manual: Backup & Checkout Release Candidate];

  ManualBackupCheckout --> ConflictsDetected{Conflicts Detected During Checkout?};

  ConflictsDetected -- Yes --> ManualConflictHandling[Manual: Complex Conflict Resolution & Reporting];
  ManualConflictHandling --> MarkNeedsImprovement[Mark Release Candidate Needs Improvement];
  MarkNeedsImprovement --> EndRework(End Process - Requires Manual Rework);

  ConflictsDetected -- No --> EndSuccess(End Process - Manual Checkout Completed Successfully);

  StopDuplicate --> EndRework;
  AbortSourceAccess --> EndRework;
  AbortValidation --> EndRework;
  AbortTargetAccess --> EndRework;
  AbortCorrupted --> EndRework;
  AbortSandboxAccess --> EndRework;