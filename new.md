# New Automed Process

```mermaid
---
config:
  layout: dagre
---
flowchart TD
  StartAutomated[Trigger Ansible Automation Platform Job] --> AutomatedPreChecks[Automated: Tag Existence & Readiness Checks];

  AutomatedPreChecks --> PreChecksOK{All Pre-Checks Pass?};
  PreChecksOK -- No --> AutomatedAbortPre[Automated: Abort - Pre-Checks Failed];
  PreChecksOK -- Yes --> AutomatedExtractValidate[Automated: Extract Objects & Validate from Source EME/Sandbox];

  AutomatedExtractValidate --> ValidationOK{Object Validation OK?};
  ValidationOK -- No --> AutomatedAbortValidation[Automated: Abort - Object Discrepancy];
  ValidationOK -- Yes --> AutomatedArtifactMgmt[Automated: Create, Push, & Verify Artifact Integrity];

  AutomatedArtifactMgmt --> ArtifactOK{Artifact Verified?};
  ArtifactOK -- No --> AutomatedAbortArtifact[Automated: Abort - Corrupted Artifact];
  ArtifactOK -- Yes --> AutomatedLoadArtifact[Automated: Load Artifact to Target EME];

  AutomatedLoadArtifact --> AutomatedSandboxOps[Automated: Target Sandbox Backup & Checkout RC];

  AutomatedSandboxOps --> ConflictsDetected[Automated: Conflicts Detected?];

  ConflictsDetected -- Yes --> AutomatedConflictResolution[Automated: Conflict Resolution Attempt & Report];
  AutomatedConflictResolution --> NeedsReview[Mark RC Needs Review - Manual Intervention Needed];
  NeedsReview --> EndAutomatedReview(End Process - Requires Manual Review);

  ConflictsDetected -- No --> EndAutomatedSuccess(End Process - Automated Checkout Completed Successfully);

  AutomatedAbortPre --> EndAutomatedFailure(End Process - Automated Failure);
  AutomatedAbortValidation --> EndAutomatedFailure;
  AutomatedAbortArtifact --> EndAutomatedFailure;