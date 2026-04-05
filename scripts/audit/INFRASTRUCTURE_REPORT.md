# INFRASTRUCTURE AUDIT REPORT
**Generated:** 2026-04-05 04:26 UTC
**Project:** IBP (shtirletzsled.ru)

---

## HEALTH SCORE: 59/100 -- POOR
> Significant issues

| Severity | Count | Points Deducted (capped) |
|----------|-------|--------------------------|
| CRITICAL | 0 | 0 |
| HIGH | 70 | 30 |
| MEDIUM | 136 | 10 |
| LOW | 13 | 1 |
| **TOTAL** | **219** | **41** |

---

## CRITICAL ISSUES (0)
*These MUST be fixed immediately -- they cause crashes or data loss*

## HIGH PRIORITY (70)
*Fix these soon -- they cause freezes, errors, or data quality issues*

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:342
- **Issue:** Function '_run_stage2_computation' has NO timeout protection
- **Fix:** Add asyncio.wait_for() or threading.Timer() timeout

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:383
- **Issue:** Function 'run_candidate_pipeline' has NO timeout protection
- **Fix:** Add asyncio.wait_for() or threading.Timer() timeout

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1498
- **Issue:** Function '_run_contact_discovery' has NO timeout protection
- **Fix:** Add asyncio.wait_for() or threading.Timer() timeout

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:315
- **Issue:** Silent exception handler at line 315 -- error swallowed
- **Fix:** Add at least: logger.warning(f'Error: {{e}}') before pass

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1250
- **Issue:** Silent exception handler at line 1250 -- error swallowed
- **Fix:** Add at least: logger.warning(f'Error: {{e}}') before pass

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:407
- **Issue:** db.session.commit() at line 407 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:991
- **Issue:** db.session.commit() at line 991 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1073
- **Issue:** db.session.commit() at line 1073 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1435
- **Issue:** db.session.commit() at line 1435 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1444
- **Issue:** db.session.commit() at line 1444 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1456
- **Issue:** db.session.commit() at line 1456 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1462
- **Issue:** db.session.commit() at line 1462 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1630
- **Issue:** db.session.commit() at line 1630 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [PIPELINE_FLOW] \app\services\candidate\pipeline.py:1677
- **Issue:** db.session.commit() at line 1677 not in try/except
- **Fix:** Wrap in try/except with db.session.rollback() on error

### [TIMEOUT_SCANNER] \app\services\candidate\contact_discovery.py:55
- **Issue:** Holehe call without overall timeout protection
- **Fix:** Wrap entire Holehe execution in 45s timeout

### [TIMEOUT_SCANNER] \app\services\candidate\contact_discovery.py:1179
- **Issue:** Holehe call without overall timeout protection
- **Fix:** Wrap entire Holehe execution in 45s timeout

### [TIMEOUT_SCANNER] \app\services\candidate\contact_discovery.py:1201
- **Issue:** Holehe call without overall timeout protection
- **Fix:** Wrap entire Holehe execution in 45s timeout

### [TIMEOUT_SCANNER] \app\services\candidate\contact_discovery.py:1213
- **Issue:** Holehe call without overall timeout protection
- **Fix:** Wrap entire Holehe execution in 45s timeout

### [TIMEOUT_SCANNER] \app\services\candidate\contact_discovery.py:1219
- **Issue:** Holehe call without overall timeout protection
- **Fix:** Wrap entire Holehe execution in 45s timeout

### [TIMEOUT_SCANNER] \app\services\candidate\contact_discovery.py:1982
- **Issue:** Holehe call without overall timeout protection
- **Fix:** Wrap entire Holehe execution in 45s timeout

### [TIMEOUT_SCANNER] \app\services\candidate\contact_discovery.py:1984
- **Issue:** Holehe call without overall timeout protection
- **Fix:** Wrap entire Holehe execution in 45s timeout

### [THREAD_SAFETY] \app\routes\api_search.py:153
- **Issue:** executor.submit(_run_tg_discover) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\candidate\behavioral_analysis.py:1098
- **Issue:** executor.submit(fn) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\candidate\social_analysis.py:555
- **Issue:** executor.submit(_run_face_search) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\candidate\social_analysis.py:555
- **Issue:** executor.submit(_run_face_search) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\candidate\social_analysis.py:555
- **Issue:** executor.submit(_run_snoop_search) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\candidate\social_analysis.py:555
- **Issue:** executor.submit(_run_maigret_search) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\candidate\social_analysis.py:555
- **Issue:** executor.submit(_run_sherlock_search) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\candidate\social_analysis.py:555
- **Issue:** executor.submit(_run_yaseeker) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\phase2\email_discovery.py:892
- **Issue:** executor.submit(check_single) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\phase2\source_manager.py:145
- **Issue:** executor.submit(source) may lack Flask app context
- **Fix:** Wrap submitted function with app.app_context()

### [THREAD_SAFETY] \app\services\candidate\behavioral_analysis.py:795
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\candidate\behavioral_analysis.py:797
- **Issue:** run_until_complete() without RuntimeError handler
- **Fix:** Add except RuntimeError to handle 'no event loop' in threads

### [THREAD_SAFETY] \app\services\phase1\telegram_discovery.py:579
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase1\telegram_discovery.py:581
- **Issue:** run_until_complete() without RuntimeError handler
- **Fix:** Add except RuntimeError to handle 'no event loop' in threads

### [THREAD_SAFETY] \app\services\phase1\telegram_discovery.py:947
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase1\telegram_discovery.py:949
- **Issue:** run_until_complete() without RuntimeError handler
- **Fix:** Add except RuntimeError to handle 'no event loop' in threads

### [THREAD_SAFETY] \app\services\phase2\combined_search.py:1077
- **Issue:** run_until_complete() without RuntimeError handler
- **Fix:** Add except RuntimeError to handle 'no event loop' in threads

### [THREAD_SAFETY] \app\services\phase2\email_discovery.py:303
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase2\email_discovery.py:400
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase2\email_discovery.py:402
- **Issue:** run_until_complete() without RuntimeError handler
- **Fix:** Add except RuntimeError to handle 'no event loop' in threads

### [THREAD_SAFETY] \app\services\phase2\email_discovery.py:465
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase2\email_discovery.py:635
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase2\email_discovery.py:813
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase2\email_discovery.py:823
- **Issue:** run_until_complete() without RuntimeError handler
- **Fix:** Add except RuntimeError to handle 'no event loop' in threads

### [THREAD_SAFETY] \app\services\phase2\forgot_password_oracle.py:1426
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase2\holehe_service.py:214
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\phase2\holehe_service.py:216
- **Issue:** run_until_complete() without RuntimeError handler
- **Fix:** Add except RuntimeError to handle 'no event loop' in threads

### [THREAD_SAFETY] \app\services\phase2\telegram_crossref.py:224
- **Issue:** new_event_loop() without set_event_loop() -- loop not registered
- **Fix:** Add asyncio.set_event_loop(loop) after creating loop

### [THREAD_SAFETY] \app\services\candidate\pipeline.py:229
- **Issue:** candidate_tasks dict is not protected by threading.Lock()
- **Fix:** Add threading.Lock() to protect concurrent task dict access

### [ERROR_COVERAGE] \app\models\business_record.py:198
- **Issue:** Bare 'except:' at line 198 -- catches EVERYTHING including SystemExit
- **Fix:** Use 'except Exception as e:' and log the error

### [ERROR_COVERAGE] \app\models\court_record.py:264
- **Issue:** Bare 'except:' at line 264 -- catches EVERYTHING including SystemExit
- **Fix:** Use 'except Exception as e:' and log the error

### [ERROR_COVERAGE] \app\routes\phase3.py:438
- **Issue:** Bare 'except:' at line 438 -- catches EVERYTHING including SystemExit
- **Fix:** Use 'except Exception as e:' and log the error

### [ERROR_COVERAGE] \app\routes\candidate_check.py:116
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:407
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:589
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:991
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1572
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1710
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1724
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1750
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1805
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1838
- **Issue:** db.session.commit() in try block without rollback on except
- **Fix:** Add 'db.session.rollback()' in except block

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:460
- **Issue:** Stage call 'egrul_future = stage0_pool.submit(_ctx(_stage0_egr' not wrapped in try/except
- **Fix:** Pipeline stage must be in try/except to prevent total pipeline crash

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:461
- **Issue:** Stage call 'bankr_future = stage0_pool.submit(_ctx(_stage0_ban' not wrapped in try/except
- **Fix:** Pipeline stage must be in try/except to prevent total pipeline crash

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:636
- **Issue:** Stage call '_ctx(_run_stage2_computation),' not wrapped in try/except
- **Fix:** Pipeline stage must be in try/except to prevent total pipeline crash

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1503
- **Issue:** Stage call 'return run_social_analysis(check)' not wrapped in try/except
- **Fix:** Pipeline stage must be in try/except to prevent total pipeline crash

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1506
- **Issue:** Stage call 'stage4_future = wave3_pool.submit(_ctx(_run_contac' not wrapped in try/except
- **Fix:** Pipeline stage must be in try/except to prevent total pipeline crash

### [ERROR_COVERAGE] \app\services\candidate\pipeline.py:1507
- **Issue:** Stage call 'stage5_future = wave3_pool.submit(_ctx(_run_social' not wrapped in try/except
- **Fix:** Pipeline stage must be in try/except to prevent total pipeline crash

### [EXTERNAL_SERVICES] EGRUL
- **Issue:** EGRUL returned HTTP 404
- **Fix:** EGRUL may be blocking requests -- check IP/headers

## MEDIUM PRIORITY (136)
*Address in next development cycle*

- **\app\models\business_record.py:196** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\routes\main.py:62** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\routes\phase3.py:436** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\bankruptcy_service.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\contact_discovery.py:1254** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\fssp_service.py:33** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\pipeline.py:303** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\pipeline.py:355** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\pipeline.py:313** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\buratino_vk_search.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\buratino_vk_search.py:323** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\ok_search_integration.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\ok_search_integration.py:31** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\telegram_discovery.py:661** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\telegram_discovery.py:786** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\vk_web_search.py:39** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\vk_web_search.py:169** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase1\yandex_search.py:195** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase2\forgot_password_oracle.py:1023** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase2\telegram_crossref.py:418** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase2\telegram_crossref.py:435** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\phase3\court_search.py:113** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\telegram\session_manager.py:87** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\telegram\session_manager.py:88** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\models\business_record.py:196** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\routes\main.py:62** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\bankruptcy_service.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\contact_discovery.py:1102** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\fssp_service.py:33** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\pipeline.py:250** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\pipeline.py:302** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\candidate\pipeline.py:260** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\buratino_vk_search.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\buratino_vk_search.py:323** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\ok_search_integration.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\ok_search_integration.py:31** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\telegram_discovery.py:633** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\telegram_discovery.py:758** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\vk_web_search.py:39** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\vk_web_search.py:149** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase1\yandex_search.py:195** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase2\forgot_password_oracle.py:1023** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase2\telegram_crossref.py:412** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase2\telegram_crossref.py:429** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\phase3\court_search.py:32** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\telegram\session_manager.py:87** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\candidate_check\app\services\telegram\session_manager.py:88** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\ok_search.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\ok_search.py:31** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\telegram_crossref.py:412** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\telegram_crossref.py:429** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\telegram_search.py:633** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\telegram_search.py:758** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\vk_search.py:26** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\vk_search.py:323** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\vk_web_search.py:39** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\people_search\app\services\vk_web_search.py:149** -- Silent optional import -- failure hidden by try/except pass
  *Fix: Log a warning when optional import fails so it's visible*

- **\app\services\candidate\pipeline.py:315** -- Exception caught but not logged at line 315
  *Fix: Add logger.warning() or logger.error() to exception handler*

- **\app\services\candidate\pipeline.py:1895** -- Exception caught but not logged at line 1895
  *Fix: Add logger.warning() or logger.error() to exception handler*

- **\app\services\candidate\pipeline.py:1250** -- Exception caught but not logged at line 1250
  *Fix: Add logger.warning() or logger.error() to exception handler*

- **\app\services\phase2\face_search_api.py:206** -- HTTP timeout too long: 60s (line 206)
  *Fix: Reduce to 15s max for external services*

- **\app\services\phase2\face_search_api.py:270** -- HTTP timeout too long: 60s (line 270)
  *Fix: Reduce to 15s max for external services*

- **\app\services\phase2\face_search_api.py:732** -- HTTP timeout too long: 60s (line 732)
  *Fix: Reduce to 15s max for external services*

- **\app\services\phase2\search4faces_service.py:204** -- HTTP timeout too long: 60s (line 204)
  *Fix: Reduce to 15s max for external services*

- **\app\services\phase3\video_analyzer.py:243** -- HTTP timeout too long: 60s (line 243)
  *Fix: Reduce to 15s max for external services*

- **\app\routes\candidate_check.py:797** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\candidate_check.py:801** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\connections.py:20** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\phase1.py:135** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\phase1.py:153** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\phase1.py:174** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\phase2.py:556** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\phase3.py:514** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\phase3.py:515** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\phase4.py:113** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\phase4.py:166** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\report.py:65** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\report.py:70** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\report.py:73** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\report.py:76** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\routes\report.py:79** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\connection_intelligence.py:63** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\connection_intelligence.py:65** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\connection_intelligence.py:137** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\dossier_generator.py:92** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\dossier_generator.py:97** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\dossier_generator.py:105** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\dossier_generator.py:110** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\dossier_generator.py:115** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\risk_scoring.py:323** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\risk_scoring.py:325** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\risk_scoring.py:326** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\candidate\behavioral_analysis.py:466** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\phase2\marketplace_scanner.py:311** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\phase2\social_graph.py:323** -- Database query with .all() and no .limit()
  *Fix: Add .limit(1000) to prevent large result sets*

- **\app\services\candidate\contact_discovery.py:324** -- Holehe only using 1 parallel workers -- too slow
  *Fix: Increase to 10-20 workers for faster execution*

- **\app\routes\api_search.py:15** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\behavioral_analysis.py:13** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\contact_discovery.py:29** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\contact_discovery.py:161** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\contact_discovery.py:181** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\contact_discovery.py:209** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:24** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:365** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:393** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:458** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:561** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:634** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:817** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:1171** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:1505** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\pipeline.py:1660** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\sanctions_check.py:22** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\candidate\social_analysis.py:14** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase1\telegram_discovery.py:9** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase1\telegram_discovery.py:22** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase1\telegram_discovery.py:229** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:23** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:90** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:399** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:816** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:844** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:846** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\email_discovery.py:892** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\phone_discovery.py:20** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\phone_discovery.py:86** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\source_manager.py:17** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\source_manager.py:35** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **\app\services\phase2\sources\holehe_check.py:51** -- ThreadPoolExecutor not used as context manager
  *Fix: Use 'with ThreadPoolExecutor() as executor:' to ensure cleanup*

- **OpenSanctions** -- OpenSanctions returned HTTP 401
  *Fix: Sanctions check may not work*

- **\app\routes\candidate_check.py:620** -- Potentially blocking operation in route: resp = http_requests.post(
  *Fix: Move heavy operations to background thread*

- **\app\routes\candidate_check.py:636** -- Potentially blocking operation in route: resp = http_requests.post(
  *Fix: Move heavy operations to background thread*

- **\app\routes\main.py:42** -- Potentially blocking operation in route: result = subprocess.run(
  *Fix: Move heavy operations to background thread*

- **\app\routes\phase1.py:372** -- Potentially blocking operation in route: profile_r = http_requests.get('https://api.vk.com/method/use
  *Fix: Move heavy operations to background thread*

- **\app\routes\phase1.py:400** -- Potentially blocking operation in route: wall_r = http_requests.get('https://api.vk.com/method/wall.g
  *Fix: Move heavy operations to background thread*

- **\app\routes\phase2.py:1095** -- Potentially blocking operation in route: time.sleep(0.2)
  *Fix: Move heavy operations to background thread*

## LOW PRIORITY (13)
*Nice to have improvements*

- \app\services\candidate\pipeline.py: 'sanctions_svc' used without None check after assignment
- \app\services\candidate\pipeline.py: 'net_searcher' used without None check after assignment
- \app\services\candidate\pipeline.py: 'stage2_executor' used without None check after assignment
- \app\services\candidate\pipeline.py: 'searcher' used without None check after assignment
- \app\services\candidate\pipeline.py: 'casebook' used without None check after assignment
- \app\services\candidate\pipeline.py: 'svc' used without None check after assignment
- \app\services\candidate\pipeline.py: 'discovery' used without None check after assignment
- \app\services\candidate\pipeline.py: 'wave3_pool' used without None check after assignment
- \app\services\candidate\pipeline.py: 'phone_intel' used without None check after assignment
- \app\services\candidate\pipeline.py: 'contact_service' used without None check after assignment
- \app\services\candidate\pipeline.py: '_beh_pool' used without None check after assignment
- \app\services\candidate\pipeline.py: 'scorer' used without None check after assignment
- \app\models\investigation.py: Potentially large JSON serialization at line 153

---

## FINDINGS BY AGENT

| Agent | Critical | High | Medium | Low | Total |
|-------|----------|------|--------|-----|-------|
| ERROR_COVERAGE | 0 | 19 | 0 | 12 | 31 |
| EXTERNAL_SERVICES | 0 | 1 | 1 | 0 | 2 |
| IMPORT_CHAIN | 0 | 0 | 57 | 0 | 57 |
| PERFORMANCE | 0 | 0 | 6 | 1 | 7 |
| PIPELINE_FLOW | 0 | 14 | 3 | 0 | 17 |
| THREAD_SAFETY | 0 | 29 | 33 | 0 | 62 |
| TIMEOUT_SCANNER | 0 | 7 | 36 | 0 | 43 |

---

## ACTION PLAN

### Immediate (fix today):

### This week:
1. \app\services\candidate\pipeline.py: Add asyncio.wait_for() or threading.Timer() timeout
2. \app\services\candidate\pipeline.py: Add asyncio.wait_for() or threading.Timer() timeout
3. \app\services\candidate\pipeline.py: Add asyncio.wait_for() or threading.Timer() timeout
4. \app\services\candidate\pipeline.py: Add at least: logger.warning(f'Error: {{e}}') before pass
5. \app\services\candidate\pipeline.py: Add at least: logger.warning(f'Error: {{e}}') before pass
6. \app\services\candidate\pipeline.py: Wrap in try/except with db.session.rollback() on error
7. \app\services\candidate\pipeline.py: Wrap in try/except with db.session.rollback() on error
8. \app\services\candidate\pipeline.py: Wrap in try/except with db.session.rollback() on error
9. \app\services\candidate\pipeline.py: Wrap in try/except with db.session.rollback() on error
10. \app\services\candidate\pipeline.py: Wrap in try/except with db.session.rollback() on error

---

## HOW TO RE-RUN THIS AUDIT
```bash
cd C:\Users\fedor\ibp
python scripts/audit/run_full_audit.py
```

Report will be regenerated at: `scripts/audit/INFRASTRUCTURE_REPORT.md`
