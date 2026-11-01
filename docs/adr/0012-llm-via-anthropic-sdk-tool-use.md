---
status: proposed
---

# The LLM layer uses the Anthropic SDK's tool use directly, without a framework

In phase 2, the LLM is called through the Anthropic Python SDK. It is given our analysis functions as tools: it decides which to call, our code computes the results, and the model explains them (ADR-0001). No orchestration framework (LangChain, LlamaIndex) sits in between, and the SDK is wrapped in a thin interface of our own. We chose this because a tool-use loop is short enough to read and test directly, and a framework would hide the part of the system we most need to understand.

This decision is provisional and will be revisited at the start of phase 2, including which model to use, checked against current Anthropic documentation and pricing.
