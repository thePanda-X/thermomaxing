from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from api import RecipeImporter

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    from fastapi.responses import FileResponse
    return FileResponse('static/index.html')

@app.get("/import")
async def import_recipe(url: str):
    async def event_generator():
        queue = asyncio.Queue()
        
        loop = asyncio.get_running_loop()
        
        def sync_callback(msg_object):
            #print("[Callback]", msg_object)
            loop.call_soon_threadsafe(queue.put_nowait, {"message": msg_object.get("message", None), "ai": msg_object.get("ai", None)})

        importer = RecipeImporter(status_callback=sync_callback)
        
        # Run the blocking task in a separate thread
        future = loop.run_in_executor(None, importer.run, url)
        
        while not future.done() or not queue.empty():
            try:
                # Wait for a message with a timeout so we can check future.done()
                message = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield f"data: {json.dumps(message)}\n\n"
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                yield f"data: {json.dumps({'message': None, 'ai': str(e)})}\n\n"
                break
        
        # Check if there was an exception in the thread
        try:
            await future
        except Exception as e:
            yield f"data: {json.dumps({'message': None, 'ai': str(e)})}\n\n"

        yield f"data: {json.dumps({'message': None, 'ai': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
