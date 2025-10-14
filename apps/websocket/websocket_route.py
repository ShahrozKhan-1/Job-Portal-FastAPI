import httpx
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends, Request
from sqlalchemy.orm import Session
from utils.ai_model import stream_ai_response
from utils.conversationMemory import ConversationMemory
from database.models import Applicant, Interview, PublicInterview, PublicInterviewAttempt
from database.database import sessionLocal, get_db
from datetime import datetime
import io
from apps.auth.utils import get_current_user
import json
import asyncio



websocket_router = APIRouter()

SAVE_INTERVIEW_URL = "http://localhost:8000/save-interview"
STT_URL = "http://localhost:8000/stt"


@websocket_router.websocket("/ws/chat/{applicant_id}")
async def websocket_chat(websocket: WebSocket, applicant_id: int):
    await websocket.accept()
    db: Session = sessionLocal()

    try:
        applicant = db.query(Applicant).filter(Applicant.id == applicant_id).first()
        if not applicant:
            await websocket.send_json({"type": "error", "message": "Applicant not found"})
            return

        interview = db.query(Interview).filter_by(applicant_id=applicant_id).first()
        if not interview:
            interview = Interview(applicant_id=applicant_id, transcript=[], question_count=0)
            db.add(interview)
            db.commit()
            db.refresh(interview)

        # Initialize memory and system prompt
        memory = ConversationMemory(applicant.job.description, applicant.resume)
        system_prompt = """
                You are a professional AI interviewer conducting a voice-based technical screening. 
                Your main objective is to assess the candidate's suitability for the job through a natural, human-like conversation.

                --- INTERVIEW STYLE ---
                - Ask **one clear question at a time**.
                - Keep each question **concise (2–3 sentences max)**.
                - Maintain **conversational flow** and give the candidate time to respond.
                - Avoid asking multiple questions in a single turn.
                - Speak in a **friendly yet professional tone**.

                --- QUESTION STRATEGY ---
                - Begin with broad, open-ended questions.
                - Gradually increase depth based on the candidate’s responses.
                - Use information from the **resume** and **job description** to tailor questions.
                - Ask practical, scenario-based questions to test applied understanding.
                - For behavioral questions, use the **STAR method** (Situation, Task, Action, Result).

                --- ADAPTATION RULES ---
                - If the candidate struggles → simplify and guide gently.
                - If the candidate excels → increase technical depth.
                - If answers are vague → ask for specific examples.
                - If short on time → focus on key job-related areas.

                --- VOICE DELIVERY ---
                - Speak naturally, with clear pronunciation and moderate pacing.
                - Use simple and understandable language.
                - Avoid technical jargon unless relevant to the candidate’s expertise.

                --- SCORING CONSIDERATIONS ---
                Assess based on:
                1. Technical knowledge
                2. Problem-solving ability
                3. Communication clarity
                4. Experience relevance
                5. Cultural fit

                --- PROHIBITED BEHAVIORS ---
                Never:
                - Ask multiple questions at once
                - Interrupt the candidate
                - Jump between unrelated topics
                - Use excessive jargon or robotic phrasing

                Begin the interview with a polite greeting and the first question.
            """


        # Load any previous conversation
        conversation_buffer = []
        for msg in interview.transcript:
            await memory.add_message(msg["sender"], msg["message"])
            conversation_buffer.append(msg)

        # Send welcome message - FIXED: removed 'message' field
        await websocket.send_json({
            "type": "welcome",
            "total_questions": 10
        })

        # Start first question if new interview
        if interview.question_count == 0:
            prompt = "Begin the interview with a brief welcome and the first question."
            ai_response = ""

            async for chunk in stream_ai_response(prompt, system_prompt, memory):
                if not chunk.startswith(("[ERROR]", "[DEBUG]")):
                    ai_response += chunk

            if ai_response.strip():
                # FIXED: Send 'question' with proper fields
                await websocket.send_json({
                    "type": "question",
                    "question": ai_response.strip(),  # Changed from 'message' to 'question'
                    "index": 1,
                    "total_questions": 10
                })
                await memory.add_message("AI", ai_response)
                conversation_buffer.append({"sender": "AI", "message": ai_response})
                interview.question_count = 1
                db.commit()

        # Main loop for remaining questions
        while interview.question_count < 10:
            try:
                data = await websocket.receive()
                user_message = ""

                # Handle text input (speech recognition)
                if data.get("type") == "websocket.receive" and data.get("text"):
                    payload = json.loads(data["text"])
                    user_message = payload.get("answer", "").strip()

                # Handle audio input (optional STT)
                elif data.get("type") == "websocket.receive" and data.get("bytes"):
                    audio_data = data["bytes"]
                    async with httpx.AsyncClient() as client:
                        response = await client.post(STT_URL, files={"file": ("audio.webm", audio_data, "audio/webm")})
                    if response.status_code == 200:
                        user_message = response.json().get("text", "").strip()

                if not user_message:
                    await websocket.send_json({"type": "ack", "message": "Please provide your answer"})
                    continue

                # Save user answer
                await memory.add_message("User", user_message)
                conversation_buffer.append({"sender": "User", "message": user_message})
                await websocket.send_json({"type": "ack", "message": "Answer received"})

                # Generate next question
                ai_response = ""
                async for chunk in stream_ai_response(user_message, system_prompt, memory):
                    if not chunk.startswith(("[ERROR]", "[DEBUG]")):
                        ai_response += chunk

                if ai_response.strip():
                    interview.question_count += 1
                    conversation_buffer.append({"sender": "AI", "message": ai_response})
                    await memory.add_message("AI", ai_response)

                    # FIXED: Send 'question' with proper fields
                    await websocket.send_json({
                        "type": "question",
                        "question": ai_response.strip(),  # Changed from 'message' to 'question'
                        "index": interview.question_count,
                        "total_questions": 10
                    })

                    interview.transcript = conversation_buffer
                    db.commit()

            except WebSocketDisconnect:
                break
            except Exception as e:
                await websocket.send_json({"type": "error", "message": f"Processing error: {str(e)}"})
                continue

        # End of interview
        completion_msg = "Thank you for completing the interview! We will review your responses soon."
        await memory.add_message("AI", completion_msg)
        conversation_buffer.append({"sender": "AI", "message": completion_msg})

        interview.transcript = conversation_buffer
        interview.completed_at = datetime.utcnow()
        db.commit()

        # FIXED: Send completion with proper field name
        await websocket.send_json({
            "type": "complete",
            "message": completion_msg,
            "summary": f"Completed {interview.question_count} questions"
        })

        # Optionally save via external API
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{SAVE_INTERVIEW_URL}/{applicant_id}", json={"transcript": conversation_buffer})
        except Exception as e:
            print(f"Error saving interview externally: {e}")

        await websocket.close()

    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": f"Connection error: {str(e)}"})
        except:
            pass
    finally:
        db.close()





@websocket_router.websocket("/ws/public-interview/{interview_id}")
async def public_interview_ws(
    websocket: WebSocket,
    interview_id: int,
    db: Session = Depends(get_db)
):
    await websocket.accept()
    
    try:
        # Get attempt_id from query parameters
        attempt_id = websocket.query_params.get("attempt_id")
        if not attempt_id:
            await websocket.send_text(json.dumps({"type": "error", "message": "Attempt ID required"}))
            await websocket.close()
            return
        
        attempt_id = int(attempt_id)

        # Fetch interview and its questions
        interview = db.query(PublicInterview).filter(PublicInterview.id == interview_id).first()
        if not interview:
            await websocket.send_text(json.dumps({"type": "error", "message": "Interview not found"}))
            await websocket.close()
            return

        questions = interview.questions or []

        # Verify attempt exists and belongs to current user
        attempt = db.query(PublicInterviewAttempt).filter_by(id=attempt_id, interview_id=interview_id).first()
        if not attempt:
            await websocket.send_text(json.dumps({"type": "error", "message": "Attempt not found"}))
            await websocket.close()
            return

        # AUTO-START: Immediately send welcome
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "question": f"Starting voice interview: {interview.title}",
            "total_questions": len(questions),
            "instructions": "The interview will start automatically. Please wait for the questions."
        }))

        # If no questions, close
        if not questions:
            await websocket.send_text(json.dumps({
                "type": "error", 
                "message": "No questions found for this interview."
            }))
            await websocket.close()
            return

        # Brief pause before starting questions
        await asyncio.sleep(1)

        # AUTO-START: Begin asking questions immediately
        for idx, question_data in enumerate(questions, start=1):
            # Handle different question formats - could be string or dict
            if isinstance(question_data, dict):
                question_text = question_data.get("question", f"Question {idx}")
            else:
                question_text = str(question_data)
            
            # Send the question
            await websocket.send_text(json.dumps({
                "type": "question",
                "question": question_text,
                "index": idx,
                "total_questions": len(questions)
            }))

            # Wait for the user's answer
            try:
                response = await asyncio.wait_for(
                    websocket.receive_text(), 
                    timeout=120.0  # 2 minutes timeout
                )
                
                data = json.loads(response)
                answer = data.get("answer")

                # Save user's response
                if answer:
                    answers = attempt.answers or {}
                    answers[f"Q{idx}"] = {
                        "question": question_text,
                        "answer": answer,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    attempt.answers = answers
                    db.commit()

                # Send acknowledgment
                await websocket.send_text(json.dumps({
                    "type": "ack",
                    "message": f"Answer received for question {idx}",
                    "index": idx
                }))

                # Brief pause before next question
                if idx < len(questions):
                    await asyncio.sleep(2)

            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "type": "timeout",
                    "message": f"Time's up for question {idx}. Moving to next question."
                }))
                # Save empty answer for timeout
                answers = attempt.answers or {}
                answers[f"Q{idx}"] = {
                    "question": question_text,
                    "answer": None,
                    "timeout": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
                attempt.answers = answers
                db.commit()
                continue
                
            except WebSocketDisconnect:
                print(f"WebSocket disconnected during question {idx}")
                return
                
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "message": "Invalid JSON received"
                }))
                continue

        # Interview completed
        await websocket.send_text(json.dumps({
            "type": "complete",
            "message": "Interview completed successfully!",
            "summary": f"You have answered all {len(questions)} questions. Thank you!"
        }))
        
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error", 
            "message": f"Server error: {str(e)}"
        }))
    finally:
        await websocket.close()