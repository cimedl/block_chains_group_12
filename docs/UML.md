# EduConsent UML class diagram

Open `uml.svg` to see the diagram. The editable Graphviz source is `uml.dot`.
The Mermaid version below can also be used in a Markdown preview that supports Mermaid.

```mermaid
classDiagram
    direction TB

    class EduConsent {
        <<Solidity contract>>
        +identities : student -> Identity
        +dataHashes : student -> DataType -> bytes32
        +consents : student -> requester -> DataType -> Consent
        +rewardBalance : student -> uint256
        +rewarded : student -> requester -> DataType -> bool
        +register(attributesHash)
        +updateIdentity(attributesHash)
        +publishData(dataType, dataHash)
        +grantConsent(requester, dataType, durationDays)
        +revokeConsent(requester, dataType)
        +hasConsent(student, requester, dataType) bool
        +requestAccess(student, dataType) bool
    }
    class Identity {
        <<struct>>
        +bytes32 attributesHash
        +bool registered
    }
    class Consent {
        <<struct>>
        +uint64 expiresAt
        +bool active
    }
    class DataType {
        <<enumeration>>
        Diploma = 0
        Transcript = 1
        Certificate = 2
    }
    class EducationDemo {
        <<Python class>>
        +web3
        +accounts
        +storage
        +measurements
        +artifact
        +contract
        +deploy()
        +send(function, sender, label)
        +register(student, identity)
        +publish(student, data_type, record)
        +grant(student, requester, data_type, days)
        +revoke(student, requester, data_type)
        +access(student, requester, data_type)
        +record_path(student, data_type)
        +advance_time(seconds)
    }
    class LocalJSONFiles {
        <<artifact>>
        Identity attributes and salt
        Education records and salt
    }
    class EduConsentTest {
        <<Solidity tests>>
        +setUp()
        24 unit tests
    }
    class EducationIntegrationTest {
        <<Python tests>>
        +setUp()
        10 integration tests
    }

    EduConsent "1" *-- "0..*" Identity : stores
    EduConsent "1" *-- "0..*" Consent : stores
    EduConsent ..> DataType : uses
    EducationDemo ..> EduConsent : deploys and calls via Web3
    EducationDemo ..> LocalJSONFiles : reads and writes
    EduConsentTest ..> EduConsent : tests
    EducationIntegrationTest ..> EducationDemo : tests
```

`+` means public. Solid lines with a filled diamond show stored structures;
dashed arrows show dependencies. `student` and `requester` are wallet addresses,
not separate classes. `LocalJSONFiles` is a file artifact, not a Python class.
Mapping keys are shown with arrows to keep them readable.

The contract emits events for identity registration and updates, data publication,
consent grants and revocations, rewards and access attempts. Those events are not
separate contracts or classes. The Python helper uses the access event, checks
current consent and compares hashes before releasing a local record. Only hashes,
permissions, rewards and event logs go on-chain; the files stay off-chain.
