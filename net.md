```mermaid
graph TD
    A[Start] --> B{Is Project <br/> SDK-style?};

      B -- No --> C[Build: <br/> msbuild.exe];
      C --> D[Test: <br/> vstest.console.exe];
      D --> E["Collect Coverage: <br/> vstest.console.exe <br/> /collect:'Code Coverage'"];
      E --> F{"Output: <br/> .coverage file <br/> (Binary)"};
      F --> G["Convert/Merge: <br/> dotnet-coverage merge <br/> (.coverage -> Cobertura XML)"];
      
      B -- Yes --> H[Build: <br/> dotnet build];
      H --> I[Test: <br/> dotnet test];
      I --> J["Collect Coverage: <br/> dotnet test <br/> --collect:'XPlat Code Coverage'<br/> (Requires Coverlet.Collector)"];
      J --> K{Output: <br/> Cobertura XML};

    G --> L[End];
    K --> L;

    style A fill:#D0F8E8,stroke:#333,stroke-width:2px;
    style L fill:#D0F8E8,stroke:#333,stroke-width:2px;
    style B fill:#FFFACD,stroke:#333,stroke-width:2px;
    style H fill:#E6EEF4,stroke:#333,stroke-width:1px;
    style I fill:#E6EEF4,stroke:#333,stroke-width:1px;
    style J fill:#E6EEF4,stroke:#333,stroke-width:1px;
    style K fill:#CCE0FF,stroke:#333,stroke-width:1px;
    style C fill:#FFE0B2,stroke:#333,stroke-width:1px;
    style D fill:#FFE0B2,stroke:#333,stroke-width:1px;
    style E fill:#FFE0B2,stroke:#333,stroke-width:1px;
    style F fill:#FFF3E0,stroke:#333,stroke-width:1px;
    style G fill:#FFE0B2,stroke:#333,stroke-width:1px