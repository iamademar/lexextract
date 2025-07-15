import { NextRequest, NextResponse } from "next/server";

export const runtime = "edge";
export const maxDuration = 30;

export async function POST(req: NextRequest) {
  try {
    const { messages, system, tools } = await req.json();
    
    // Get the last message from the conversation
    const lastMessage = messages[messages.length - 1];
    
    // Extract text content from the message (handle both string and array formats)
    let userMessage = "";
    if (typeof lastMessage?.content === "string") {
      userMessage = lastMessage.content;
    } else if (Array.isArray(lastMessage?.content)) {
      // Handle array format from assistant-ui
      userMessage = lastMessage.content
        .filter((item: any) => item.type === "text")
        .map((item: any) => item.text)
        .join(" ");
    }
    
    console.log("Received message:", lastMessage?.content);
    console.log("Extracted message:", userMessage);
    
    // Make request to FastAPI backend
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    const response = await fetch(`${backendUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: userMessage,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`FastAPI request failed: ${response.status}`);
    }
    
    const data = await response.json();
    console.log("FastAPI response:", data);
    
    // Convert FastAPI response to assistant-ui format
    const assistantResponse = data.response || "I'm sorry, I couldn't process your request.";
    
    // Create a streaming response by sending text chunks word by word
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder();
        
        // Split the response into words and send them one by one
        const words = assistantResponse.split(' ');
        
        words.forEach((word: string, index: number) => {
          const textChunk = index === 0 ? word : ' ' + word;
          controller.enqueue(encoder.encode(`0:${JSON.stringify(textChunk)}\n`));
        });
        
        // Send finish chunk
        controller.enqueue(encoder.encode(`d:{"finishReason":"stop","usage":{"promptTokens":0,"completionTokens":0,"totalTokens":0}}\n`));
        
        controller.close();
      },
    });
    
    return new Response(stream, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
    
  } catch (error) {
    console.error("Error in chat API:", error);
    return NextResponse.json(
      { error: "Failed to process chat request" },
      { status: 500 }
    );
  }
}
