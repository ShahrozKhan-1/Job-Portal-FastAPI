import httpx
from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends, Request
from sqlalchemy.orm import Session
from utils.ai_model import stream_ai_response, evaluate_interview_ai
from utils.conversationMemory import ConversationMemory
from database.models import Applicant, Interview, PublicInterview, PublicInterviewAttempt
from database.database import sessionLocal, get_db
from datetime import datetime
from apps.dashboard.dashboard import extract_pdf_text
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
                - Keep each question **concise (2-3 sentences max)**.
                - Maintain **conversational flow** and give the candidate time to respond.
                - Avoid asking multiple questions in a single turn.
                - Speak in a **friendly yet professional tone**.

                --- QUESTION STRATEGY ---
                - Begin with broad, open-ended questions.
                - Gradually increase depth based on the candidate's responses.
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
        if interview.question_count == 0:
            prompt = "Begin the interview with a brief welcome and the first question."
            ai_response = ""

            async for chunk in stream_ai_response(prompt, system_prompt, memory):
                if not chunk.startswith(("[ERROR]", "[DEBUG]")):
                    ai_response += chunk

            if ai_response.strip():
                await websocket.send_json({
                    "type": "question",
                    "question": ai_response.strip(),
                    "index": 1,
                    "total_questions": 10
                })
                await memory.add_message("AI", ai_response)
                conversation_buffer.append({"sender": "AI", "message": ai_response})
                interview.question_count = 1
                db.commit()
        while interview.question_count < 10:
            try:
                data = await websocket.receive()
                user_message = ""
                if data.get("type") == "websocket.receive" and data.get("text"):
                    payload = json.loads(data["text"])
                    user_message = payload.get("answer", "").strip()
                elif data.get("type") == "websocket.receive" and data.get("bytes"):
                    audio_data = data["bytes"]
                    async with httpx.AsyncClient() as client:
                        response = await client.post(STT_URL, files={"file": ("audio.webm", audio_data, "audio/webm")})
                    if response.status_code == 200:
                        user_message = response.json().get("text", "").strip()

                if not user_message:
                    await websocket.send_json({"type": "ack", "message": "Please provide your answer"})
                    continue
                await memory.add_message("User", user_message)
                conversation_buffer.append({"sender": "User", "message": user_message})
                await websocket.send_json({"type": "ack", "message": "Answer received"})

                ai_response = ""
                async for chunk in stream_ai_response(user_message, system_prompt, memory):
                    if not chunk.startswith(("[ERROR]", "[DEBUG]")):
                        ai_response += chunk

                if ai_response.strip():
                    interview.question_count += 1
                    conversation_buffer.append({"sender": "AI", "message": ai_response})
                    await memory.add_message("AI", ai_response)
                    await websocket.send_json({
                        "type": "question",
                        "question": ai_response.strip(),
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
        completion_msg = "Thank you for completing the interview! We will review your responses soon."
        await memory.add_message("AI", completion_msg)
        conversation_buffer.append({"sender": "AI", "message": completion_msg})

        interview.transcript = conversation_buffer
        interview.completed_at = datetime.utcnow()
        db.commit()
        await websocket.send_json({
            "type": "complete",
            "message": completion_msg,
            "summary": f"Completed {interview.question_count} questions"
        })
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
        attempt_id = websocket.query_params.get("attempt_id")
        if not attempt_id:
            await websocket.send_text(json.dumps({"type": "error", "message": "Attempt ID required"}))
            await websocket.close()
            return
        
        attempt_id = int(attempt_id)
        interview = db.query(PublicInterview).filter(PublicInterview.id == interview_id).first()
        if not interview:
            await websocket.send_text(json.dumps({"type": "error", "message": "Interview not found"}))
            await websocket.close()
            return

        attempt = db.query(PublicInterviewAttempt).filter_by(id=attempt_id, interview_id=interview_id).first()
        if not attempt:
            await websocket.send_text(json.dumps({"type": "error", "message": "Attempt not found"}))
            await websocket.close()
            return
        job_description = getattr(interview, 'description', 'No job description provided')
        resume_text = extract_pdf_text(attempt.resume) or "No resume provided"
        # Initialize conversation memory for AI
        memory = ConversationMemory(job_desc=job_description, resume=resume_text)
        
        # System prompt for AI interviewer
        system_prompt = f"""
        You are a professional AI interviewer conducting a job interview for: {interview.title}
        
        Interview Context:
        - Position: {interview.title}
        - Description: {getattr(interview, 'description', 'No description provided')}
        - Candidate's Resume: {attempt.resume}
        
        Your role:
        1. Start with an introductory question
        2. Ask relevant technical and behavioral questions based on the position
        3. Ask one question at a time
        4. Provide natural follow-up questions based on the candidate's responses
        5. Maintain professional tone
        6. End the interview appropriately when sufficient questions have been asked
        
        Format your responses as natural conversation. Ask only one question per response.
        """

        await websocket.send_text(json.dumps({
            "type": "welcome",
            "message": f"Starting AI-powered interview: {interview.title}",
            "instructions": "The AI interviewer will ask questions one by one. Please respond to each question."
        }))

        # Get first question from AI
        first_question = ""
        async for chunk in stream_ai_response(
            user_message="Start the interview with your first question.",
            system_prompt=system_prompt,
            memory=memory
        ):
            first_question += chunk

        if not first_question:
            await websocket.send_text(json.dumps({
                "type": "error", 
                "message": "Failed to generate initial question."
            }))
            await websocket.close()
            return

        # Initialize transcript
        transcript = []
        question_count = 0
        max_questions = 10  # Maximum number of questions to prevent infinite loops

        # Send first question
        question_count += 1
        await websocket.send_text(json.dumps({
            "type": "question",
            "question": first_question.strip(),
            "index": question_count,
            "total_questions": f"AI-driven (up to {max_questions})"
        }))

        # Store first question in transcript
        transcript.append({
            "question": first_question.strip(),
            "timestamp": datetime.utcnow().isoformat()
        })

        # Main interview loop
        while question_count < max_questions:
            try:
                # Receive candidate's answer
                response = await asyncio.wait_for(websocket.receive_text(), timeout=120.0)
                data = json.loads(response)
                answer = data.get("answer", "").strip()

                if not answer:
                    await websocket.send_text(json.dumps({
                        "type": "warning",
                        "message": "Please provide an answer to continue."
                    }))
                    continue

                # Store answer in transcript
                if transcript and len(transcript) >= question_count:
                    transcript[question_count - 1]["answer"] = answer

                await websocket.send_text(json.dumps({
                    "type": "ack",
                    "message": f"Answer received for question {question_count}",
                    "index": question_count
                }))

                # Check if interview should end (based on AI response or user signal)
                if data.get("end_interview") or "thank you" in answer.lower()[-100:]:
                    break

                # Get next question from AI
                next_question = ""
                async for chunk in stream_ai_response(
                    user_message=answer,
                    system_prompt=system_prompt,
                    memory=memory
                ):
                    next_question += chunk

                next_question = next_question.strip()

                # Check if AI indicates end of interview
                if not next_question or any(phrase in next_question.lower() for phrase in 
                    ["that concludes", "end of interview", "thank you for your time", "final thoughts"]):
                    break

                # Send next question
                question_count += 1
                await websocket.send_text(json.dumps({
                    "type": "question",
                    "question": next_question,
                    "index": question_count,
                    "total_questions": f"AI-driven (up to {max_questions})"
                }))

                # Store next question in transcript
                transcript.append({
                    "question": next_question,
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Brief pause before next question
                await asyncio.sleep(1)

            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "type": "timeout",
                    "message": f"Time's up for question {question_count}. Moving to next question."
                }))
                
                # Store timeout in transcript
                if transcript and len(transcript) >= question_count:
                    transcript[question_count - 1]["answer"] = None
                    transcript[question_count - 1]["timeout"] = True
                
                # Get follow-up question after timeout
                next_question = ""
                async for chunk in stream_ai_response(
                    user_message="[Candidate did not respond within time limit. Please continue with the next question.]",
                    system_prompt=system_prompt,
                    memory=memory
                ):
                    next_question += chunk

                question_count += 1
                await websocket.send_text(json.dumps({
                    "type": "question",
                    "question": next_question.strip(),
                    "index": question_count,
                    "total_questions": f"AI-driven (up to {max_questions})"
                }))

                transcript.append({
                    "question": next_question.strip(),
                    "timestamp": datetime.utcnow().isoformat()
                })

            except WebSocketDisconnect:
                print(f"WebSocket disconnected during question {question_count}")
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "message": "Invalid JSON received"
                }))
                continue

        # Interview completed - update database
        await websocket.send_text(json.dumps({
            "type": "complete",
            "message": "Interview completed successfully! Evaluating your answers..."
        }))

        # Update the PublicInterviewAttempt with transcript
        attempt.transcript = transcript
        db.commit()

        # AI Evaluation
        try:
            evaluation_prompt = """
            You are an AI interviewer evaluator. Evaluate the following interview transcript.
            Consider:
            - Technical knowledge and skills
            - Communication skills
            - Problem-solving approach
            - Professionalism
            - Relevance to the position
            
            Return a JSON with:
            {
                "score": <float between 0 and 100>,
                "feedback": "<detailed textual feedback highlighting strengths and areas for improvement>"
            }
            """
            
            # Convert transcript to evaluation format
            eval_transcript = []
            for qa in transcript:
                eval_transcript.append({
                    "question": qa.get("question"),
                    "answer": qa.get("answer", "No answer provided")
                })

            # Use your existing evaluation function
            result = await evaluate_interview_ai(eval_transcript, evaluation_prompt)
            
            # Update attempt with score and feedback
            attempt.score = result.get("score")
            attempt.feedback = result.get("feedback")
            db.commit()
            
            await websocket.send_text(json.dumps({
                "type": "evaluation",
                "score": result.get("score"),
                "feedback": result.get("feedback")
            }))
            
        except Exception as e:
            print(f"Evaluation error: {str(e)}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"AI Evaluation failed: {str(e)}"
            }))

        await websocket.send_text(json.dumps({
            "type": "complete",
            "message": "Interview completed and evaluated successfully!",
            "total_questions": question_count
        }))

    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error", 
            "message": f"Server error: {str(e)}"
        }))
    finally:
        await websocket.close()