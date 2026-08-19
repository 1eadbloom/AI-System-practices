# Skill: LangGraph 代理架構與應用程式開發

## Metadata
- **知識領域**：大型語言模型 (LLM) 應用程式架構、狀態型應用程式開發、代理協作
- **資料來源數量**：21 份文件
- **最後更新時間**：2026-06-23
- **適用 Agent 類型**：開發助手 / 技術顧問

## Overview（一段話摘要）
LangGraph 代理架構是基於 LangChain 的框架，用於構建狀態管理和多步驟應用程式，透過 directed graph 處理 loops 和 agent 邏輯。核心概念包括狀態、資源、工具和提示。MCP（模型控制平台）提供了一個標準化的可重用能力，允許用戶明確選擇和附加上下文中的內容，並通過工具與模型進行互動，最終打造基於 LLM 的狀態型、多步驟應用程式。

## Core Concepts（核心概念）
1.  **LangGraph**：LangGraph 是一個基於 LangChain 的框架，用於構建狀態管理和多步驟應用程式，透過 directed graph 來處理 loops 和 agent 邏輯 [來源: langgraph\01_core_concepts.txt, 段落 0]。
2.  **狀態 (State)**：在 LangGraph 中，狀態是應用程式的核心概念，允許模型在多個步驟中追蹤資訊和做出決策 [來源: mcp\05_tools_resources_prompts_design.txt, 段落 2]。
3.  **資源 (Resources)**：資源是指使用者可以明確選擇並附加到上下文中的內容，例如文件或設定，以提供模型參考的資訊 [來源: mcp\05_tools_resources_prompts_design.txt, 段落 2 & 5]。
4.  **工具 (Tools)**：工具是模型可以自主呼叫的 Python 函數，例如查詢資料庫或執行計算，模型根據對話決策呼叫它們 [來源: langgraph\05_tool_calling_react.txt, 段落 4 & mcp\05_tools_resources_prompts_design.txt, 段落 1]。
5.  **工具描述 (Tool Descriptions)**：工具的清晰、明確的描述對於模型準確地選擇和使用這些工具至關重要 [來源: langgraph\05_tool_calling_react.txt, 段落 4 & mcp\05_tools_resources_prompts_design.txt, 段落 8]。
6.  **平行工具呼叫 (Parallel tool calls)**：同時呼叫多個工具是有效的策略，提升了效率和靈活性 [來源: langgraph\05_tool_calling_react.txt, 段落 4]。
7.  **資源註冊 (Resource Registration)**：資源通過 `@mcp.resource(uri_template)` 註冊，讓模型可以輕鬆存取 [來源: mcp\05_tools_resources_prompts_design.txt, 段落 5]。
8.  **工作範例 (Worked example)**：以專案管理伺服器為例，展示了工具、資源和提示的組合 [來源: mcp\05_tools_resources_prompts_design.txt, 段落 5]。
9. **選擇工具、資源或提示 (Choosing Between Tools, Resources, and Prompts)**：  選擇正確的工具、資源或提示對應用程式的設計和使用者體驗至關重要 [來源: mcp\05_tools_resources_prompts_design.txt, 段落 0]。
10. **工具的運作方式 (How tools work)**: 模型在選擇是否呼叫工具以及傳入的參數時處於控制權 [來源: mcp\05_tools_resources_prompts_design.txt, 段落 2]。
11. **資源的運作方式 (How resources work)**: 資源的的使用者可以明確選擇並附加到上下文，不依賴模型自行決定 [來源: mcp\05_tools_resources_prompts_design.txt, 段落 2]。
12. **prompt 的運作方式 (How prompts work)**: 提示是模板，將資訊組合在一起 [來源: mcp\05_tools_resources_prompts_design.txt, 段落 1]。

## Key Trends（最新趨勢）
1.  **多代理協作架構的標準化:**  LangGraph 提供了一種標準化的框架，使得多代理協作變得更容易設計和實施。
2.  **狀態管理的重要性日益增加:**  在多步驟應用程式中，有效地管理狀態是至關重要的，LangGraph 提供了強大的狀態管理能力。
3.  **工具和資源的精確定義:**  清晰、精確的工具和資源定義可以顯著提高模型成功呼叫它們的準確率。
4.  **以資源為中心的設計:** 越來越多的應用程式採用以資源為中心的設計模式，使用者可以更方便地提供模型所需的資訊。
5.  **工具鏈優化:**  透過精細地設計和整合工具，可以有效地提升應用程式的效率和性能。

## Key Entities（重要實體）
**框架/函式庫名稱：**
*   FastAPI [來源: fastapi\01_core_concepts.txt, 段落 4]
*   LangChain [來源: langgraph\05_tool_calling_react.txt, 段落 4]
*   Pydantic [來源: fastapi\07_building_agent_backends.txt, 段落 9]
*   OpenAPI [來源: fastapi\01_core_concepts.txt, 段落 4]
*   langchain\_core [來源: langgraph\05_tool_calling_react.txt, 段落 4]

**關鍵 API 或類別名稱：**
*   ItemOut [來源: fastapi\01_core_concepts.txt, 段落 4]
*   @app.post "/items/", response_model=ItemOut) [來源: fastapi\01_core_concepts.txt, 段落 4]
*   get\_weather [來源: langgraph\05_tool_calling_react.txt, 段落 4]
*   OAuth2PasswordBearer [來源: fastapi\04_authentication_security.txt, 段落 7]
*   Depends [來源: fastapi\07_building_agent_backends.txt, 段落 9]

**設計模式名稱：**
*   Resource [來源: mcp\05_tools_resources_prompts_design.txt, 段落 2]
*   Prompt [來源: mcp\05_tools_resources_prompts_design.txt, 段落 3]
*   Tool [來源: langgraph\05_tool_calling_react.txt, 段落 4]

**協定/標準名稱：**
*   HTTP GET [來源: mcp\01_protocol_overview.txt, 段落 7]
*   OAuth2 [來源: fastapi\04_authentication_security.txt, 段落 7]
*   OpenAPI [來源: fastapi\01_core_concepts.txt, 段落 4]

## Methodology & Best Practices（方法論與最佳實踐）
1.  **設計階段：** 應將 LangGraph 框架用於構建大型語言模型 (LLM) 應用程式的狀態管理和多步驟流程。
2.  **資源管理：**  明確設計資源以允許使用者主動選擇和附加上下文，以提供模型參考的資訊。
3.  **工具設計：**  設計工具時，定義清晰的說明和類型提示，以促進模型的有效呼叫。
4.  **狀態管理策略：**  針對應用程式的複雜性和狀態需求，制定狀態管理策略。
5.  **版本控制：** 採用版本控制方法來跟踪和管理 LangGraph 應用程式的修改，以確保可追蹤性和可恢復性。

## Knowledge Gaps & Limitations（知識邊界）
由於提供的文檔主要涵蓋 MCP 框架中的資源、工具和提示概念，以及它們在語言模型中的使用方式，因此知識庫沒有涉及例如：
*   具體 API 版本細節。
*   特定雲端平台部署的相關資訊。
*   效能調校的具體數據。

## Example Q&A（代表性問答）
1.  **問題:** 在 LangGraph 中，State 如何在多步驟應用程式中協調並管理？
    **回答:** State 是 LangGraph 框架的核心概念，允許模型在多個步驟中追蹤資訊和做出決策，通過 directed graph 來處理 loops 和 agent 邏輯。
2.  **問題:** MCP 協議中，Tools、Resources 和 Prompts 三種基本組件的區別是什麼，以及在設計一個整合了多個工具的 MCP 伺服器時，應該如何選擇這些組件？
    **回答:** Tools 允許模型自主呼叫 Python 函數，Resources 允許使用者明確選擇附加上下文內容，Prompts 是模板，將資訊組合在一起；設計時，需要根據業務需求和工具的複雜度進行選擇。
3.  **問題:** 如何使用 Pydantic 模型在 FastAPI 伺服器中驗證和文件化對 agent-specific endpoints 的工具呼叫數據形狀？
    **回答:** 可以通過在 FastAPI 路由中使用 `response_model` 參數，並配置 Pydantic 模型來驗證和文件化，同時確保數據的正確格式。
4.  **問題:**  LangGraph 如何利用 directed graph 來建模 stateful、多步驟應用程式，並解決傳統 prompt-chain 結構無法解決的循環、分支和長期代理行為問題？
     **回答:**  LangGraph 的 directed graph 允許模型在狀態變化的基礎上，正確地處理循環邏輯，並透過明確定義的節點和邊來控制 agent 流程，避免 prompt-chain 結構所無法解決的問題。
5.  **問題:** 當一個 LangGraph 代理的工具定義或 MCP 工具方案需要暴露給前端時，Pydantic 模型的作用是什麼？
    **回答:** Pydantic 模型用於定義工具的輸入參數類型，並確保前端對工具的呼叫符合預期的格式，從而增強了工具的可用性和可靠性。

## Source References（來源索引）
- fastapi\01_core_concepts.txt
- langgraph\01_core_concepts.txt
- langgraph\04_multi_agent_architectures.txt
- langgraph\05_tool_calling_react.txt
- mcp\01_protocol_overview.txt
- mcp\05_tools_resources_prompts_design.txt
- fastapi\07_building_agent_backends.txt
- fastapi\04_authentication_security.txt

### 完整資料來源清單（自動生成）

| 子主題 | 檔案路徑 | 類型 | 收錄日期 |
| --- | --- | --- | --- |
| fastapi | `data/raw/fastapi\01_core_concepts.md` | MD | 2026-06-23 |
| fastapi | `data/raw/fastapi\02_dependency_injection.md` | MD | 2026-06-23 |
| fastapi | `data/raw/fastapi\03_async_concurrency.md` | MD | 2026-06-23 |
| fastapi | `data/raw/fastapi\04_authentication_security.md` | MD | 2026-06-23 |
| fastapi | `data/raw/fastapi\05_middleware_errors_lifespan.md` | MD | 2026-06-23 |
| fastapi | `data/raw/fastapi\06_testing.md` | MD | 2026-06-23 |
| fastapi | `data/raw/fastapi\07_building_agent_backends.md` | MD | 2026-06-23 |
| langgraph | `data/raw/langgraph\01_core_concepts.md` | MD | 2026-06-23 |
| langgraph | `data/raw/langgraph\02_persistence_checkpointing.md` | MD | 2026-06-23 |
| langgraph | `data/raw/langgraph\03_human_in_the_loop.md` | MD | 2026-06-23 |
| langgraph | `data/raw/langgraph\04_multi_agent_architectures.md` | MD | 2026-06-23 |
| langgraph | `data/raw/langgraph\05_tool_calling_react.md` | MD | 2026-06-23 |
| langgraph | `data/raw/langgraph\06_streaming_deployment.md` | MD | 2026-06-23 |
| langgraph | `data/raw/langgraph\07_faq_pitfalls.md` | MD | 2026-06-23 |
| mcp | `data/raw/mcp\01_protocol_overview.md` | MD | 2026-06-23 |
| mcp | `data/raw/mcp\02_building_server_python.md` | MD | 2026-06-23 |
| mcp | `data/raw/mcp\03_clients_host_integration.md` | MD | 2026-06-23 |
| mcp | `data/raw/mcp\04_authentication_remote_servers.md` | MD | 2026-06-23 |
| mcp | `data/raw/mcp\05_tools_resources_prompts_design.md` | MD | 2026-06-23 |
| mcp | `data/raw/mcp\06_langgraph_integration.md` | MD | 2026-06-23 |
| mcp | `data/raw/mcp\07_faq_pitfalls.md` | MD | 2026-06-23 |
